"""Site Monitor — FastAPI application entrypoint."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import settings
from app.database import init_db
from app.routers import dashboard, sites
from app.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("monitor")


def _ensure_dirs() -> None:
    if settings.database_url.startswith("sqlite"):
        path = settings.database_url.split(":///")[-1]
        if path and path != ":memory:":
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_dirs()
    await init_db()
    start_scheduler()
    logger.info("Site Monitor v%s started", __version__)
    try:
        yield
    finally:
        shutdown_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(title="Site Monitor", version=__version__, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(dashboard.router)
    app.include_router(sites.router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Liveness check endpoint."""
        return {"status": "healthy", "version": __version__}

    return app


app = create_app()
