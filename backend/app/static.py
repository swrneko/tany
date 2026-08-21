from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.errors import ApiError


def mount_frontend(app: FastAPI, dist_dir: Path | None) -> None:
    """Serve the built SPA from the API process.

    Vite compiles to static files, so no second Node container is needed in
    production. In development the directory is absent and Vite serves the UI
    itself, proxying /api here.
    """
    if dist_dir is None or not (dist_dir / "index.html").is_file():
        return

    index = dist_dir / "index.html"

    @app.get("/{spa_path:path}", include_in_schema=False)
    async def serve_spa(spa_path: str) -> FileResponse:
        if spa_path.startswith("api/"):
            # Registered after the API routers, so this only catches unmatched
            # /api paths. They must stay JSON: a client parsing index.html as an
            # error response is a genuinely baffling bug report.
            raise ApiError(404, "not_found", "No such endpoint.")

        candidate = (dist_dir / spa_path).resolve()
        if spa_path and candidate.is_file() and candidate.is_relative_to(dist_dir.resolve()):
            return FileResponse(candidate)

        return FileResponse(index)
