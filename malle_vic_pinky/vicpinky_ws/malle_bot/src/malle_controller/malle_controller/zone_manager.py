#!/usr/bin/env python3
"""
ZoneManager — 구역 데이터 관리 + Nav2 keepout mask 동적 업데이트.

동작 흐름:
  1. load(): 서버 GET /zones 로 초기 데이터 로드 (실패 시 YAML fallback)
  2. WS ZONE_UPDATED 이벤트 수신 → _apply_patch() → zones dict 갱신
  3. RESTRICTED / MAINTENANCE zone 이 변경되면 _publish_keepout_mask() 호출
     → 기존 기본 맵 위에 zone 폴리곤을 occupied(100) 으로 그린 OccupancyGrid 생성
     → /keepout_mask 토픽 publish
     → Nav2 local/global costmap keepout_layer 가 자동으로 갱신

CAUTION / CONGESTED zone 은 keepout 에 포함하지 않음:
  - 통과는 허용, 속도 제한만 필요
  - mission_executor / nav_core 에서 zones dict 를 직접 참조해 속도 조절

Nav2 파라미터 변경 불필요:
  - nav2_params.yaml keepout_layer.map_topic: "/keepout_mask" 이미 설정됨
  - map_subscribe_transient_local: True → latched 토픽처럼 동작

WKT 폴리곤 파싱 (shapely 없는 환경 대비 내장 파서 사용):
  "POLYGON((x1 y1, x2 y2, x3 y3, x1 y1))" → [(x1,y1), (x2,y2), ...]
"""

import asyncio
import json
import math
import os
import threading
from pathlib import Path
from typing import Optional

import yaml

try:
    import websockets
    _HAS_WS = True
except ImportError:
    _HAS_WS = False

try:
    import rclpy
    from nav_msgs.msg import OccupancyGrid
    from std_msgs.msg import Header
    from builtin_interfaces.msg import Time
    _HAS_ROS = True
except ImportError:
    _HAS_ROS = False

from malle_controller.api_client import ApiClient


_FALLBACK_PATH = Path(__file__).parent.parent / 'config' / 'fallback' / 'zones.yaml'

# zone_type 값 중 keepout(통행 금지) 으로 처리할 타입
_KEEPOUT_TYPES = {"RESTRICTED", "MAINTENANCE"}


# ---------------------------------------------------------------------------
# Minimal WKT POLYGON parser (shapely 없이 동작)
# ---------------------------------------------------------------------------

def _parse_wkt_polygon(wkt: str) -> list[tuple[float, float]]:
    """
    "POLYGON((x1 y1, x2 y2, ...))" → [(x1,y1), (x2,y2), ...]
    외곽 링만 사용 (홀 무시).
    """
    wkt = wkt.strip()
    start = wkt.find("((")
    end = wkt.find("))")
    if start == -1 or end == -1:
        # POLYGON(x1 y1, ...) 형태도 허용
        start = wkt.find("(")
        end = wkt.rfind(")")
        if start == -1:
            return []
        coords_str = wkt[start + 1:end]
    else:
        coords_str = wkt[start + 2:end]

    coords = []
    for pair in coords_str.split(","):
        parts = pair.strip().split()
        if len(parts) >= 2:
            try:
                coords.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return coords


# ---------------------------------------------------------------------------
# Grid rasterizer — polygon fill (scanline)
# ---------------------------------------------------------------------------

def _fill_polygon_on_grid(
    grid: list[int],
    width: int,
    height: int,
    polygon: list[tuple[float, float]],
    origin_x: float,
    origin_y: float,
    resolution: float,
    value: int = 100,
):
    """
    맵 좌표계 폴리곤을 grid (row-major, width×height) 에 rasterize.
    grid[row * width + col] = value (occupied)
    """
    if not polygon:
        return

    # 폴리곤 꼭짓점을 grid 셀 좌표로 변환
    px = [(v[0] - origin_x) / resolution for v in polygon]
    py = [(v[1] - origin_y) / resolution for v in polygon]

    min_row = max(0, int(min(py)))
    max_row = min(height - 1, int(max(py)) + 1)

    n = len(px)
    for row in range(min_row, max_row + 1):
        intersections = []
        for i in range(n):
            j = (i + 1) % n
            yi, yj = py[i], py[j]
            if (yi <= row < yj) or (yj <= row < yi):
                # x at y=row
                t = (row - yi) / (yj - yi)
                x_int = px[i] + t * (px[j] - px[i])
                intersections.append(x_int)
        intersections.sort()
        for k in range(0, len(intersections) - 1, 2):
            col_start = max(0, int(math.ceil(intersections[k])))
            col_end = min(width - 1, int(intersections[k + 1]))
            for col in range(col_start, col_end + 1):
                grid[row * width + col] = value


# ---------------------------------------------------------------------------
# ZoneManager
# ---------------------------------------------------------------------------

class ZoneManager:
    """
    구역 데이터를 관리하고 Nav2 keepout mask 를 동적으로 업데이트한다.

    zones dict 포맷 (서버 API 응답 기반):
      {
        <id: int>: {
          "id": int,
          "name": str,
          "zone_type": "RESTRICTED" | "MAINTENANCE" | "CAUTION" | "CONGESTED",
          "polygon_wkt": "POLYGON((x1 y1, ...))",
          "is_active": bool,
          "priority": "LOW" | "MEDIUM" | "HIGH",
          "speed_limit_mps": float | None,
          "one_way": bool | None,
          "enhanced_avoidance": bool | None,
        },
        ...
      }
    """

    def __init__(
        self,
        api_client: ApiClient,
        ws_url: str | None = None,
        logger=None,
        ros_node=None,
        map_width: int = 225,
        map_height: int = 190,
        map_resolution: float = 0.02,
        map_origin_x: float = 0.0,
        map_origin_y: float = 0.0,
    ):
        self._api = api_client
        self._ws_url = ws_url
        self._log = logger
        self._node = ros_node          # rclpy Node (keepout publish 에 사용)
        self._ws_thread: threading.Thread | None = None

        # Map metadata (nav2_params.yaml / map.yaml 과 일치해야 함)
        # 기본값: 2.5m×2m 맵, 0.02m/cell → 125×100 cells
        # 실제 맵 크기에 맞게 생성자 인자로 조정
        self._map_width = map_width
        self._map_height = map_height
        self._map_resolution = map_resolution
        self._map_origin_x = map_origin_x
        self._map_origin_y = map_origin_y

        self.zones: dict[int, dict] = {}

        # ROS publisher
        self._keepout_pub = None
        if _HAS_ROS and self._node is not None:
            self._keepout_pub = self._node.create_publisher(
                OccupancyGrid, "/keepout_mask", 1
            )
            self._info("[ZoneManager] /keepout_mask publisher 준비")

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def load(self):
        """시작 시 한 번 호출. 서버 실패 시 YAML fallback."""
        try:
            data = self._api.get('/zones')
            self.zones = {z['id']: z for z in data}
            self._info(f'[ZoneManager] {len(self.zones)}개 구역 로드 완료')
        except Exception as e:
            self._warn(f'[ZoneManager] 서버 로드 실패 ({e}), fallback 사용')
            self.zones = self._load_fallback()

        # 초기 keepout mask publish
        self._publish_keepout_mask()

        if self._ws_url and _HAS_WS:
            self._start_ws_listener()

    def is_in_keepout(self, x: float, y: float) -> bool:
        """주어진 맵 좌표가 활성 keepout zone 안에 있으면 True."""
        for zone in self.zones.values():
            if not zone.get("is_active"):
                continue
            if zone.get("zone_type") not in _KEEPOUT_TYPES:
                continue
            polygon = _parse_wkt_polygon(zone.get("polygon_wkt", ""))
            if polygon and _point_in_polygon(x, y, polygon):
                return True
        return False

    def get_speed_limit(self, x: float, y: float) -> float | None:
        """
        주어진 좌표에서 적용되는 최소 속도 제한 반환.
        해당 좌표가 여러 CAUTION/CONGESTED zone 에 걸치면 가장 낮은 값.
        None 이면 제한 없음.
        """
        limit = None
        for zone in self.zones.values():
            if not zone.get("is_active"):
                continue
            if zone.get("zone_type") not in ("CAUTION", "CONGESTED"):
                continue
            spd = zone.get("speed_limit_mps")
            if spd is None:
                continue
            polygon = _parse_wkt_polygon(zone.get("polygon_wkt", ""))
            if polygon and _point_in_polygon(x, y, polygon):
                if limit is None or spd < limit:
                    limit = spd
        return limit

    # -----------------------------------------------------------------------
    # WS listener
    # -----------------------------------------------------------------------

    def _start_ws_listener(self):
        self._ws_thread = threading.Thread(
            target=self._ws_loop, daemon=True, name='zone_ws'
        )
        self._ws_thread.start()

    def _ws_loop(self):
        asyncio.run(self._ws_recv())

    async def _ws_recv(self):
        try:
            async with websockets.connect(self._ws_url) as ws:
                self._info(f'[ZoneManager] WS 연결: {self._ws_url}')
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        # manager.py 포맷: {"type": ..., "payload": ..., "timestamp": ...}
                        if msg.get("type") == "ZONE_UPDATED":
                            self._apply_patch(msg.get("payload", {}))
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            self._warn(f'[ZoneManager] WS 오류: {e}')

    def _apply_patch(self, payload: dict):
        """
        서버 ZONE_UPDATED payload 처리.
        payload 포맷:
          { "action": "created"|"updated"|"deleted", "zone": {...} }
          deleted 시: { "action": "deleted", "zone": {"id": <id>} }
        """
        action = payload.get("action")
        zone = payload.get("zone", {})
        zone_id = zone.get("id")

        if action in ("created", "updated") and zone_id is not None:
            self.zones[zone_id] = zone
            self._info(f'[ZoneManager] 구역 {action}: id={zone_id} ({zone.get("name")})')
            # keepout 관련 타입이면 즉시 mask 재발행
            if zone.get("zone_type") in _KEEPOUT_TYPES:
                self._publish_keepout_mask()

        elif action == "deleted" and zone_id is not None:
            removed = self.zones.pop(zone_id, None)
            if removed:
                self._info(f'[ZoneManager] 구역 삭제: id={zone_id}')
                if removed.get("zone_type") in _KEEPOUT_TYPES:
                    self._publish_keepout_mask()

        # CAUTION/CONGESTED 변경은 get_speed_limit() 가 자동으로 반영하므로
        # 별도 처리 불필요

    # -----------------------------------------------------------------------
    # Keepout mask publisher
    # -----------------------------------------------------------------------

    def _publish_keepout_mask(self):
        """
        활성 RESTRICTED / MAINTENANCE zone 을 occupied(100) 으로 그린
        OccupancyGrid 를 /keepout_mask 로 publish.

        Nav2 keepout_layer (StaticLayer, map_topic: /keepout_mask) 가
        이 토픽을 수신해 costmap 을 갱신.
        """
        if not _HAS_ROS or self._keepout_pub is None:
            self._info("[ZoneManager] ROS 없음 — keepout mask publish 스킵")
            return

        w = self._map_width
        h = self._map_height
        res = self._map_resolution
        ox = self._map_origin_x
        oy = self._map_origin_y

        # 기본값: 전부 free(0)
        grid: list[int] = [0] * (w * h)

        # 활성 keepout zone 만 rasterize
        for zone in self.zones.values():
            if not zone.get("is_active"):
                continue
            if zone.get("zone_type") not in _KEEPOUT_TYPES:
                continue
            polygon = _parse_wkt_polygon(zone.get("polygon_wkt", ""))
            _fill_polygon_on_grid(grid, w, h, polygon, ox, oy, res, value=100)

        msg = OccupancyGrid()
        msg.header = Header()
        msg.header.frame_id = "map"
        now = self._node.get_clock().now().to_msg()
        msg.header.stamp = now

        msg.info.resolution = res
        msg.info.width = w
        msg.info.height = h
        msg.info.origin.position.x = ox
        msg.info.origin.position.y = oy
        msg.info.origin.position.z = 0.0
        msg.info.origin.orientation.w = 1.0

        msg.data = grid

        self._keepout_pub.publish(msg)
        keepout_count = sum(
            1 for z in self.zones.values()
            if z.get("is_active") and z.get("zone_type") in _KEEPOUT_TYPES
        )
        self._info(
            f"[ZoneManager] /keepout_mask publish: {w}×{h}, "
            f"keepout zones={keepout_count}"
        )

    # -----------------------------------------------------------------------
    # Fallback loader
    # -----------------------------------------------------------------------

    @staticmethod
    def _load_fallback() -> dict:
        """
        YAML fallback 포맷 (zones.yaml):
          zones:
            - id: 1
              name: "...'
              zone_type: RESTRICTED
              polygon_wkt: "POLYGON((...))"
              is_active: true
        """
        if _FALLBACK_PATH.exists():
            with open(_FALLBACK_PATH) as f:
                data = yaml.safe_load(f) or {}
            return {z['id']: z for z in data.get('zones', [])}
        return {}

    # -----------------------------------------------------------------------
    # Logger helpers
    # -----------------------------------------------------------------------

    def _info(self, msg: str):
        if self._log:
            self._log.info(msg)

    def _warn(self, msg: str):
        if self._log:
            self._log.warn(msg)


# ---------------------------------------------------------------------------
# Point-in-polygon (ray casting)
# ---------------------------------------------------------------------------

def _point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside