"""Dashboard: overview of all monitored sites."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.services import sites as sites_service
from app.templating import templates

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request, session: AsyncSession = Depends(get_session)
):
    rows = await sites_service.dashboard_rows(session)
    up = sum(1 for r in rows if r["site"].current_status == "up")
    down = sum(1 for r in rows if r["site"].current_status == "down")
    unknown = sum(1 for r in rows if r["site"].current_status == "unknown")
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "rows": rows,
            "total": len(rows),
            "up": up,
            "down": down,
            "unknown": unknown,
            "telegram_enabled": settings.telegram_enabled,
            "default_interval": settings.default_interval_minutes,
            "error": request.query_params.get("error"),
        },
    )
