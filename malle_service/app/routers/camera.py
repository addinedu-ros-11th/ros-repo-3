"""
로봇 카메라 스트리밍 중계.
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

router = APIRouter()

STREAM_MAX_FPS = 15

class _FrameStore:
    """로봇별 최신 JPEG 프레임을 보관하는 인메모리 버퍼."""

    def __init__(self):
        self._frames: dict[int, bytes] = {}
        # asyncio.Lock은 이벤트루프 종속 → get_or_create 패턴 사용
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def put(self, robot_id: int, frame: bytes) -> None:
        async with self._get_lock():
            self._frames[robot_id] = frame

    async def get(self, robot_id: int) -> Optional[bytes]:
        async with self._get_lock():
            return self._frames.get(robot_id)

    def robots_with_frames(self) -> list[int]:
        return list(self._frames.keys())


frame_store = _FrameStore()

@router.post("/robots/{robot_id}/camera/frame")
async def receive_frame(robot_id: int, request: Request):
    """bridge_node가 JPEG 바이너리를 직접 POST 하는 엔드포인트.

    UDP 모드로 전환 시 이 라우트 대신 malle_service lifespan에서 UDP
    리스너 태스크를 시작하고 frame_store.put() 을 호출하면 됩니다.
    """
    body = await request.body()
    if body:
        await frame_store.put(robot_id, body)
    return {"ok": True}


NO_FRAME_TIMEOUT = 10.0


async def _mjpeg_gen(robot_id: int):
    """버퍼에 쌓인 프레임을 MJPEG 형식으로 무한 생성."""
    min_interval = 1.0 / STREAM_MAX_FPS
    loop = asyncio.get_event_loop()
    no_frame_since = loop.time()

    while True:
        t0 = loop.time()
        frame = await frame_store.get(robot_id)

        if frame is None:
            if loop.time() - no_frame_since > NO_FRAME_TIMEOUT:
                return
            await asyncio.sleep(0.5)
            continue

        no_frame_since = loop.time()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame
            + b"\r\n"
        )

        elapsed = loop.time() - t0
        wait = min_interval - elapsed
        if wait > 0:
            await asyncio.sleep(wait)


@router.get("/robots/{robot_id}/camera/stream")
async def camera_stream(robot_id: int):
    """MJPEG 스트림 — <img src="..."> 또는 브라우저 직접 접근."""
    return StreamingResponse(
        _mjpeg_gen(robot_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/robots/{robot_id}/camera/snapshot")
async def camera_snapshot(robot_id: int):
    """최신 프레임 1장 반환 (JPEG)."""
    frame = await frame_store.get(robot_id)
    if not frame:
        return JSONResponse({"error": "No frame available"}, status_code=404)
    return StreamingResponse(iter([frame]), media_type="image/jpeg")


@router.get("/robots/camera/active")
async def active_cameras():
    """현재 프레임이 있는 로봇 ID 목록."""
    return {"robot_ids": frame_store.robots_with_frames()}
