# mock_bridge.py
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.post("/bridge/{path:path}")
async def catch_all(path: str, body: dict = {}):
    print(f"[MOCK BRIDGE] /{path} → {body}")
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9100)