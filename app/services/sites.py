"""CRUD operations and uptime statistics for monitored sites."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Check, Site
from app.utils import utcnow


class SiteError(Exception):
    """Raised when site input is invalid."""


async def create_site(
    session: AsyncSession,
    *,
    name: str,
    url: str,
    interval_minutes: int,
    expected_status: int | None = None,
) -> Site:
    url = (url or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise SiteError("URL must start with http:// or https://")
    if interval_minutes < 1:
        raise SiteError("Check interval must be at least 1 minute.")
    if expected_status is not None and not (100 <= expected_status <= 599):
        raise SiteError("Expected status code must be between 100 and 599.")
    name = (name or "").strip() or url

    site = Site(
        name=name[:128],
        url=url[:2048],
        interval_minutes=interval_minutes,
        expected_status=expected_status,
    )
    session.add(site)
    await session.commit()
    await session.refresh(site)
    return site


async def delete_site(session: AsyncSession, site: Site) -> None:
    await session.delete(site)
    await session.commit()


async def get_site(session: AsyncSession, site_id: int) -> Site | None:
    return await session.get(Site, site_id)


async def list_sites(session: AsyncSession) -> list[Site]:
    stmt = select(Site).order_by(Site.created_at.desc())
    return list((await session.scalars(stmt)).all())


async def uptime_stats(
    session: AsyncSession, site_id: int, since: datetime | None = None
) -> dict:
    conditions = [Check.site_id == site_id]
    if since is not None:
        conditions.append(Check.checked_at >= since)
    stmt = select(
        func.count(Check.id),
        func.sum(case((Check.is_up.is_(True), 1), else_=0)),
        func.avg(case((Check.is_up.is_(True), Check.response_time_ms))),
    ).where(*conditions)
    total, up, avg_resp = (await session.execute(stmt)).one()
    total = int(total or 0)
    up = int(up or 0)
    return {
        "total": total,
        "up": up,
        "down": total - up,
        "uptime_pct": (up / total * 100) if total else None,
        "avg_response_ms": round(avg_resp, 1) if avg_resp is not None else None,
    }


async def recent_checks(
    session: AsyncSession, site_id: int, limit: int = 50
) -> list[Check]:
    stmt = (
        select(Check)
        .where(Check.site_id == site_id)
        .order_by(Check.checked_at.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def dashboard_rows(session: AsyncSession) -> list[dict]:
    sites = await list_sites(session)
    since = utcnow() - timedelta(hours=24)
    rows: list[dict] = []
    for site in sites:
        stats = await uptime_stats(session, site.id, since=since)
        rows.append(
            {
                "site": site,
                "uptime_24h": stats["uptime_pct"],
                "avg_response_ms": stats["avg_response_ms"],
                "checks_24h": stats["total"],
            }
        )
    return rows
