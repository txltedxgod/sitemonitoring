"""APScheduler setup: a single recurring tick that runs due checks."""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.services.monitor import run_due_checks

logger = logging.getLogger("monitor.scheduler")
scheduler = AsyncIOScheduler()


async def _tick() -> None:
    try:
        checked = await run_due_checks()
        if checked:
            logger.info("Tick: checked %d site(s)", checked)
    except Exception:  # noqa: BLE001
        logger.exception("Scheduler tick failed")


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        _tick,
        "interval",
        seconds=settings.tick_seconds,
        id="monitor_tick",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (tick every %ds)", settings.tick_seconds)


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
