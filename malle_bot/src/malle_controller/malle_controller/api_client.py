#!/usr/bin/env python3
"""
api_client.py  —  httpx 래퍼 (malle_service REST 호출)

동기 호출 기반의 얇은 래퍼.
타임아웃, 에러 처리 등 공통 로직을 담는다.
"""

import httpx


class ApiClient:
    """
    malle_service REST API 클라이언트.

    Parameters
    ----------
    base_url : str
        예) "http://localhost:8000/api/v1"
    timeout  : float
        초 단위 요청 타임아웃 (기본 5.0)
    logger   : rclpy Logger (선택)
    """

    def __init__(self, base_url: str, timeout: float = 5.0, logger=None):
        self._base    = base_url.rstrip('/')
        self._timeout = timeout
        self._log     = logger

    # ── 기본 HTTP 메서드 ─────────────────────────────────────────────────────

    def get(self, path: str, params: dict | None = None) -> list | dict:
        url = self._url(path)
        with httpx.Client(timeout=self._timeout) as c:
            resp = c.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, body: dict | None = None) -> list | dict:
        url = self._url(path)
        with httpx.Client(timeout=self._timeout) as c:
            resp = c.post(url, json=body)
        resp.raise_for_status()
        return resp.json()

    def patch(self, path: str, body: dict | None = None) -> list | dict:
        url = self._url(path)
        with httpx.Client(timeout=self._timeout) as c:
            resp = c.patch(url, json=body)
        resp.raise_for_status()
        return resp.json()

    def delete(self, path: str) -> list | dict:
        url = self._url(path)
        with httpx.Client(timeout=self._timeout) as c:
            resp = c.delete(url)
        resp.raise_for_status()
        return resp.json()

    # ── Robot ────────────────────────────────────────────────────────────────

    def update_robot_state(self, robot_id: int, x_m: float, y_m: float,
                           theta_rad: float, speed_mps: float,
                           battery_pct: int, motion_state: str) -> dict:
        """PATCH /robots/{id}/state — bridge_node 0.5Hz 상태 push"""
        return self.patch(f'/robots/{robot_id}/state', {
            'x_m':          x_m,
            'y_m':          y_m,
            'theta_rad':    theta_rad,
            'speed_mps':    speed_mps,
            'battery_pct':  battery_pct,
            'motion_state': motion_state,
        })

    # ── Guide queue ──────────────────────────────────────────────────────────

    def get_guide_queue(self, session_id: int) -> list[dict]:
        """GET /sessions/{id}/guide-queue"""
        return self.get(f'/sessions/{session_id}/guide-queue')

    def update_guide_item(self, session_id: int, item_id: int,
                          status: str) -> dict:
        """
        PATCH /sessions/{id}/guide-queue/{item_id}
        status: PENDING | ARRIVED | DONE | SKIPPED
        """
        return self.patch(
            f'/sessions/{session_id}/guide-queue/{item_id}',
            {'status': status},
        )

    # ── Session ──────────────────────────────────────────────────────────────

    def update_session_status(self, session_id: int, status: str) -> dict:
        """PATCH /sessions/{id}/status"""
        return self.patch(f'/sessions/{session_id}/status', {'status': status})

    def get_session(self, session_id: int) -> dict:
        """GET /sessions/{id}"""
        return self.get(f'/sessions/{session_id}')

    # ── POI ─────────────────────────────────────────────────────────────────

    def list_pois(self) -> list[dict]:
        """GET /pois"""
        return self.get('/pois')

    # ── Zone ─────────────────────────────────────────────────────────────────

    def list_zones(self) -> list[dict]:
        """GET /zones"""
        return self.get('/zones')

    # ── Events ───────────────────────────────────────────────────────────────

    def post_event(self, robot_id: int, event_type: str,
                   severity: str = 'INFO',
                   session_id: int | None = None,
                   payload: dict | None = None) -> dict:
        """POST /events"""
        body: dict = {
            'robot_id':    robot_id,
            'type':        event_type,
            'severity':    severity,
        }
        if session_id is not None:
            body['session_id'] = session_id
        if payload:
            body['payload_json'] = payload
        return self.post('/events', body)

    # ── 내부 ─────────────────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        return self._base + '/' + path.lstrip('/')