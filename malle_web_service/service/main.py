#!/usr/bin/env python3
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients: List[WebSocket] = []

class WebData(BaseModel):
    message_id: str
    ai_result: dict
    timing: Dict[str, float]

@app.post("/web/update")
async def update_web(data: WebData):
    message = {
        'type': 'robot_update',
        'data': {
            'message_id': data.message_id,
            'ai_result': data.ai_result,
            'timing': data.timing,
            'received_at': datetime.now().isoformat()
        }
    }

    disconnected = []
    for client in connected_clients:
        try:
            await client.send_json(message)
        except Exception:
            disconnected.append(client)

    for client in disconnected:
        connected_clients.remove(client)

    return {"status": "broadcasted", "clients": len(connected_clients)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

@app.get("/")
def read_root():
    return {
        "status": "malle_web_service running",
        "port": 8001,
        "connected_clients": len(connected_clients)
    }

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
