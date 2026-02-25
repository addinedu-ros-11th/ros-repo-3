"""공통 설정 및 헬퍼."""

import json
import requests

BASE_URL = "http://localhost:8000/api/v1"


def ok(label: str, resp: requests.Response) -> dict:
    if resp.status_code < 300:
        print(f"  [PASS] {label} ({resp.status_code})")
    else:
        print(f"  [FAIL] {label} ({resp.status_code}): {resp.text[:200]}")
    try:
        return resp.json()
    except Exception:
        return {}


def get(path: str, **kwargs):
    return requests.get(f"{BASE_URL}{path}", **kwargs)


def post(path: str, body: dict = None, **kwargs):
    return requests.post(f"{BASE_URL}{path}", json=body, **kwargs)


def patch(path: str, body: dict = None, **kwargs):
    return requests.patch(f"{BASE_URL}{path}", json=body, **kwargs)


def delete(path: str, **kwargs):
    return requests.delete(f"{BASE_URL}{path}", **kwargs)


def health():
    resp = requests.get("http://localhost:8000/health")
    if resp.status_code == 200:
        print("  [PASS] health check (200)")
    else:
        print(f"  [FAIL] health check ({resp.status_code})")
        raise SystemExit("서버가 실행 중이지 않습니다. 먼저 서버를 시작하세요.")
