#!/usr/bin/env python3
"""
api_client.py  –  httpx 래퍼 (malle_service REST 호출)

동기 호출 기반의 얇은 래퍼.
타임아웃, 에러 처리, 재시도 등 공통 로직을 담는다.
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
        self._base = base_url.rstrip('/')
        self._timeout = timeout
        self._log = logger

    # ── 기본 메서드 ──────────────────────────────────────────────────────────
    def get(self, path: str, params: dict | None = None) -> list | dict:
        """GET 요청 후 JSON 반환."""
        url = self._url(path)
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, body: dict | None = None) -> list | dict:
        """POST 요청 후 JSON 반환."""
        url = self._url(path)
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, json=body)
        resp.raise_for_status()
        return resp.json()

    def patch(self, path: str, body: dict | None = None) -> list | dict:
        """PATCH 요청 후 JSON 반환."""
        url = self._url(path)
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.patch(url, json=body)
        resp.raise_for_status()
        return resp.json()

    # ── 도메인 특화 메서드 ───────────────────────────────────────────────────
    def report_status(self, robot_id: str, status: str,
                      battery: float = 0.0, task_id: str = '') -> dict:
        """로봇 상태를 서버에 보고한다."""
        return self.patch(f'/robots/{robot_id}/status', {
            'status':   status,
            'battery':  battery,
            'task_id':  task_id,
        })

    def complete_task(self, task_id: str, result: str) -> dict:
        """태스크 완료를 서버에 알린다."""
        return self.post(f'/tasks/{task_id}/complete', {'result': result})

    # ── 내부 ─────────────────────────────────────────────────────────────────
    def _url(self, path: str) -> str:
        return self._base + '/' + path.lstrip('/')
