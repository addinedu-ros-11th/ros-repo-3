#!/usr/bin/env python3
import os
import yaml
import asyncio
import threading
from pathlib import Path

try:
    import websockets
    _HAS_WS = True
except ImportError:
    _HAS_WS = False

from malle_controller.api_client import ApiClient


_FALLBACK_PATH = Path(__file__).parent.parent / 'config' / 'fallback' / 'zones.yaml'


class ZoneManager:
    """
    구역 데이터를 관리한다.

    zones 포맷:
      {
        "zone_id": {
          "name": "매장 A",
          "type": "rect",   # rect | circle | polygon
          "x": 1.0, "y": 2.0, "w": 3.0, "h": 2.0
        },
        ...
      }
    """

    def __init__(self, api_client: ApiClient, ws_url: str | None = None,
                 logger=None):
        self._api    = api_client
        self._ws_url = ws_url
        self._log    = logger
        self.zones: dict = {}
        self._ws_thread: threading.Thread | None = None

    def load(self):
        """시작 시 한 번 호출. 서버 실패 시 fallback."""
        try:
            data = self._api.get('/zones')
            self.zones = {z['id']: z for z in data}
            self._info(f'[ZoneManager] {len(self.zones)}개 구역 로드 완료')
        except Exception as e:
            self._warn(f'[ZoneManager] 서버 로드 실패 ({e}), fallback 사용')
            self.zones = self._load_fallback()

        if self._ws_url and _HAS_WS:
            self._start_ws_listener()

    def _start_ws_listener(self):
        self._ws_thread = threading.Thread(
            target=self._ws_loop, daemon=True, name='zone_ws'
        )
        self._ws_thread.start()

    def _ws_loop(self):
        asyncio.run(self._ws_recv())

    async def _ws_recv(self):
        import json
        try:
            async with websockets.connect(self._ws_url) as ws:
                self._info(f'[ZoneManager] WS 연결: {self._ws_url}')
                async for raw in ws:
                    payload = json.loads(raw)
                    self._apply_patch(payload)
        except Exception as e:
            self._warn(f'[ZoneManager] WS 오류: {e}')

    def _apply_patch(self, payload: dict):
        """
        서버 패치 포맷 예시:
          { "action": "upsert", "zone": { "id": "z1", ... } }
          { "action": "delete", "zone_id": "z1" }
        """
        action = payload.get('action')
        if action == 'upsert':
            z = payload['zone']
            self.zones[z['id']] = z
            self._info(f'[ZoneManager] 구역 갱신: {z["id"]}')
        elif action == 'delete':
            zid = payload.get('zone_id')
            self.zones.pop(zid, None)
            self._info(f'[ZoneManager] 구역 삭제: {zid}')

    @staticmethod
    def _load_fallback() -> dict:
        if _FALLBACK_PATH.exists():
            with open(_FALLBACK_PATH) as f:
                data = yaml.safe_load(f) or {}
            return {z['id']: z for z in data.get('zones', [])}
        return {}

    def _info(self, msg: str):
        if self._log:
            self._log.info(msg)

    def _warn(self, msg: str):
        if self._log:
            self._log.warn(msg)
