"""Site management: add, delete, detail view and manual re-check."""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services import sites as sites_service
from app.services.monitor import check_single
from app.services.sites import SiteError
from app.templating import templates
from app.utils import utcnow

router = APIRouter(tags=["sites"])


@router.post("/sites")
async def add_site(
    name: str = Form(""),
    url: str = Form(...),
    interval_minutes: int = Form(...),
    expected_status: str = Form(""),
    session: AsyncSession = Depends(get_session),
):
    parsed_status: int | None = None
    expected_status = (expected_status or "").strip()
    if expected_status:
        try:
            parsed_status = int(expected_status)
        except ValueError:
            return RedirectResponse(
                f"/?error={quote('Expected status must be a number.')}",
                status_code=303,
            )
    try:
        await sites_service.create_site(
            session,
            name=name,
            url=url,
            interval_minutes=interval_minutes,
            expected_status=parsed_status,
        )
    except SiteError as exc:
        return RedirectResponse(f"/?error={quote(str(exc))}", status_code=303)
    return RedirectResponse("/", status_code=303)


@router.get("/sites/{site_id}", response_class=HTMLResponse)
async def site_detail(
    site_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    site = await sites_service.get_site(session, site_id)
    if not site:
        return RedirectResponse("/", status_code=303)

    now = utcnow()
    stats_24h = await sites_service.uptime_stats(
        session, site_id, since=now - timedelta(hours=24)
    )
    stats_7d = await sites_service.uptime_stats(
        session, site_id, since=now - timedelta(days=7)
    )
    stats_all = await sites_service.uptime_stats(session, site_id)
    checks = await sites_service.recent_checks(session, site_id, limit=50)

    return templates.TemplateResponse(
        "site_detail.html",
        {
            "request": request,
            "site": site,
            "stats_24h": stats_24h,
            "stats_7d": stats_7d,
            "stats_all": stats_all,
            "checks": checks,
        },
    )


@router.post("/sites/{site_id}/check-now")
async def check_now(
    site_id: int, session: AsyncSession = Depends(get_session)
):
    site = await sites_service.get_site(session, site_id)
    if site:
        await check_single(session, site)
        await session.commit()
        return RedirectResponse(f"/sites/{site_id}", status_code=303)
    return RedirectResponse("/", status_code=303)


@router.post("/sites/{site_id}/delete")
async def delete_site(
    site_id: int, session: AsyncSession = Depends(get_session)
):
    site = await sites_service.get_site(session, site_id)
    if site:
        await sites_service.delete_site(session, site)
    return RedirectResponse("/", status_code=303)
