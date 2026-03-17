#!/usr/bin/env python3
"""Run malle_web_service on port 8001."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
