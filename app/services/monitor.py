"""Core monitoring logic: run due checks and fire state-change alerts."""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import Check, Site
from app.services import checker, telegram
from app.services.checker import CheckResult
from app.utils import utcnow

logger = logging.getLogger("monitor.engine")


def _format_alert(site: Site, result: CheckResult, recovered: bool) -> str:
    if recovered:
        return (
            f"\u2705 <b>{site.name}</b> is back UP\n{site.url}\n"
            f"Response: {result.response_time_ms} ms "
            f"(HTTP {result.status_code})"
        )
    return (
        f"\U0001F534 <b>{site.name}</b> is DOWN\n{site.url}\n"
        f"Reason: {result.error or 'unknown'}"
    )


async def check_single(session: AsyncSession, site: Site) -> Check:
    """Check one site, persist the result and notify on status transitions."""
    result = await checker.check_site(site.url, site.expected_status)
    previous = site.current_status
    new_status = "up" if result.is_up else "down"

    check = Check(
        site_id=site.id,
        is_up=result.is_up,
        status_code=result.status_code,
        response_time_ms=result.response_time_ms,
        error=result.error,
    )
    session.add(check)
    site.current_status = new_status
    site.last_checked_at = utcnow()
    await session.flush()

    alert: str | None = None
    if new_status == "down" and previous in ("up", "unknown"):
        alert = _format_alert(site, result, recovered=False)
    elif new_status == "up" and previous == "down":
        alert = _format_alert(site, result, recovered=True)

    if alert:
        await telegram.send_message(alert)
        logger.info("Status change for %s: %s -> %s", site.name, previous, new_status)

    logger.info(
        "Checked %s -> %s (HTTP %s, %s ms)",
        site.url,
        new_status,
        result.status_code,
        result.response_time_ms,
    )
    return check


async def run_due_checks() -> int:
    """Find sites whose next check is due and check them sequentially.

    Sequential execution keeps a single AsyncSession safe (it must not be used
    concurrently) and preserves notification ordering.
    """
    async with async_session() as session:
        now = utcnow()
        sites = list(
            (await session.scalars(select(Site).where(Site.is_active.is_(True)))).all()
        )
        due = [
            s
            for s in sites
            if s.last_checked_at is None
            or s.last_checked_at + timedelta(minutes=s.interval_minutes) <= now
        ]
        if not due:
            return 0
        for site in due:
            try:
                await check_single(session, site)
            except Exception:  # noqa: BLE001
                logger.exception("Check failed for %s", site.url)
        await session.commit()
        return len(due)
