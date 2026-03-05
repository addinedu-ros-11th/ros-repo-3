"""
malle_web_service - Static file serving for 3 React SPAs.
Serves /mobile/*, /robot/*, /admin/* with SPA fallback.
Port: 8001
"""

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

app = FastAPI(title="Mall-E Web Service", version="0.1.0")

# Paths to built UI directories
UI_DIR = Path(__file__).parent.parent / "ui"
MOBILE_DIR = UI_DIR / "mobile" / "dist"
ROBOT_DIR = UI_DIR / "robot" / "dist"
ADMIN_DIR = UI_DIR / "admin" / "dist"

# Root redirect
@app.get("/")
async def root():
    return HTMLResponse(
        """<html><body>
        <h2>Mall-E Web Service</h2>
        <ul>
            <li><a href="/mobile/">Mobile App</a></li>
            <li><a href="/robot/">Robot UI</a></li>
            <li><a href="/admin/">Admin Dashboard</a></li>
        </ul>
        </body></html>"""
    )

# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "service": "malle_web_service"}


def _mount_spa(app: FastAPI, path_prefix: str, dist_dir: Path):
    """Mount a React SPA with static assets and fallback to index.html."""

    if not dist_dir.exists():
        @app.get(f"/{path_prefix}/{{rest_of_path:path}}")
        async def not_built(rest_of_path: str, _prefix=path_prefix):
            return HTMLResponse(
                f"<h3>{_prefix} UI not built yet.</h3>"
                f"<p>Run <code>cd malle_web_service/ui/{_prefix} && npm run build</code></p>",
                status_code=503,
            )
        return

    # Mount static assets (js, css, images, etc.)
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount(
            f"/{path_prefix}/assets",
            StaticFiles(directory=str(assets_dir)),
            name=f"{path_prefix}_assets",
        )

    # SPA fallback: any route under /prefix/* returns index.html
    @app.get(f"/{path_prefix}/{{rest_of_path:path}}")
    async def spa_fallback(request: Request, rest_of_path: str, _dir=dist_dir):
        # Try to serve the exact file first
        file_path = _dir / rest_of_path
        if rest_of_path and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise, return index.html (SPA routing)
        index = _dir / "index.html"
        if index.exists():
            return FileResponse(index)
        return HTMLResponse("<h3>index.html not found</h3>", status_code=404)

    # Handle /prefix (without trailing slash)
    @app.get(f"/{path_prefix}")
    async def spa_root(_dir=dist_dir):
        index = _dir / "index.html"
        if index.exists():
            return FileResponse(index)
        return HTMLResponse("<h3>index.html not found</h3>", status_code=404)


# Mount all three SPAs
_mount_spa(app, "mobile", MOBILE_DIR)
_mount_spa(app, "robot", ROBOT_DIR)
_mount_spa(app, "admin", ADMIN_DIR)
