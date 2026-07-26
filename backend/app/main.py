from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.core.db import init_db

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)


def mount_spa(target_app: FastAPI, static_dir: Path) -> None:
    """Serve the built Vue SPA (backend/static/, populated by the frontend
    build stage in the root Dockerfile). No-op if the directory doesn't
    exist (local dev: frontend runs on its own Vite dev server there).
    """
    if not static_dir.is_dir():
        return

    target_app.mount(
        "/assets", StaticFiles(directory=static_dir / "assets"), name="static-assets"
    )

    # StaticFiles alone 404s on unknown paths; Vue Router's history mode
    # needs every non-API, non-asset path to resolve to index.html so the
    # client-side router can take over.
    @target_app.get("/{full_path:path}", include_in_schema=False, tags=["spa"])
    async def serve_spa(full_path: str) -> FileResponse:
        if full_path.startswith(f"{settings.API_V1_STR.lstrip('/')}/"):
            raise HTTPException(status_code=404)
        return FileResponse(static_dir / "index.html")


mount_spa(app, STATIC_DIR)
