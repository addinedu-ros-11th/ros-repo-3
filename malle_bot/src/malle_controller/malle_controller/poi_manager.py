#!/usr/bin/env python3
import yaml
from pathlib import Path
from ament_index_python.packages import get_package_share_directory

from malle_controller.api_client import ApiClient


_FALLBACK_PATH = Path(get_package_share_directory('malle_controller')) / 'config' / 'fallback' / 'pois.yaml'


class PoiManager:
    """
    POI 데이터를 관리한다.

    pois 포맷:
      {
        "poi_id": {
          "name": "카페 A",
          "x": 1.5,
          "y": 3.2,
          "yaw": 0.0,
          "zone_id": "zone_cafe"
        },
        ...
      }
    """

    def __init__(self, api_client: ApiClient, logger=None):
        self._api = api_client
        self._log = logger
        self.pois: dict = {}

    def load(self):
        """시작 시 한 번 호출. 서버 실패 시 fallback."""
        try:
            data = self._api.get('/pois')
            self.pois = {str(p['id']): self._normalize(p) for p in data}
            self._info(f'[PoiManager] {len(self.pois)}개 POI 로드 완료')
            self._info(f'[PoiManager] 로드된 ID 목록: {list(self.pois.keys())}')
        except Exception as e:
            self._warn(f'[PoiManager] 서버 로드 실패 ({e}), fallback 사용')
            self.pois = self._load_fallback()
            self._info(f'[PoiManager] fallback {len(self.pois)}개 POI 로드 완료 (경로: {_FALLBACK_PATH})')

    def get(self, poi_id: str) -> dict | None:
        return self.pois.get(poi_id)

    def list_by_zone(self, zone_id: str) -> list[dict]:
        return [p for p in self.pois.values() if p.get('zone_id') == zone_id]

    def all_ids(self) -> list[str]:
        return list(self.pois.keys())

    @staticmethod
    def _normalize(p: dict) -> dict:
        """서버 필드(x_m, y_m)와 fallback 필드(x, y)를 통일."""
        return {
            **p,
            'x': p.get('x') if p.get('x') is not None else p.get('x_m', 0.0),
            'y': p.get('y') if p.get('y') is not None else p.get('y_m', 0.0),
            'yaw': p.get('yaw', 0.0),
        }

    @staticmethod
    def _load_fallback() -> dict:
        if _FALLBACK_PATH.exists():
            with open(_FALLBACK_PATH) as f:
                data = yaml.safe_load(f) or {}
            return {str(p['id']): PoiManager._normalize(p) for p in data.get('pois', [])}
        return {}

    def _info(self, msg: str):
        if self._log:
            self._log.info(msg)

    def _warn(self, msg: str):
        if self._log:
            self._log.warn(msg)
