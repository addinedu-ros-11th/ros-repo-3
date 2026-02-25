#!/usr/bin/env python3
import yaml
from pathlib import Path

from malle_controller.api_client import ApiClient


_FALLBACK_PATH = Path(__file__).parent.parent / 'config' / 'fallback' / 'pois.yaml'


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
            self.pois = {p['id']: p for p in data}
            self._info(f'[PoiManager] {len(self.pois)}개 POI 로드 완료')
        except Exception as e:
            self._warn(f'[PoiManager] 서버 로드 실패 ({e}), fallback 사용')
            self.pois = self._load_fallback()

    def get(self, poi_id: str) -> dict | None:
        return self.pois.get(poi_id)

    def list_by_zone(self, zone_id: str) -> list[dict]:
        return [p for p in self.pois.values() if p.get('zone_id') == zone_id]

    def all_ids(self) -> list[str]:
        return list(self.pois.keys())

    @staticmethod
    def _load_fallback() -> dict:
        if _FALLBACK_PATH.exists():
            with open(_FALLBACK_PATH) as f:
                data = yaml.safe_load(f) or {}
            return {p['id']: p for p in data.get('pois', [])}
        return {}

    def _info(self, msg: str):
        if self._log:
            self._log.info(msg)

    def _warn(self, msg: str):
        if self._log:
            self._log.warn(msg)
