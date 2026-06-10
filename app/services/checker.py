"""Performs a single HTTP health check against a site."""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.config import settings

_USER_AGENT = "SiteMonitor/1.0 (+https://github.com)"


@dataclass(slots=True)
class CheckResult:
    is_up: bool
    status_code: int | None
    response_time_ms: float | None
    error: str | None


async def check_site(
    url: str,
    expected_status: int | None = None,
    timeout: int | None = None,
) -> CheckResult:
    timeout = timeout or settings.request_timeout
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=timeout
        ) as client:
            resp = await client.get(url, headers={"User-Agent": _USER_AGENT})
        elapsed = (time.perf_counter() - start) * 1000
        if expected_status:
            is_up = resp.status_code == expected_status
        else:
            is_up = 200 <= resp.status_code < 400
        error = None if is_up else f"Unexpected HTTP {resp.status_code}"
        return CheckResult(is_up, resp.status_code, round(elapsed, 1), error)
    except Exception as exc:  # noqa: BLE001 - any network error means "down"
        elapsed = (time.perf_counter() - start) * 1000
        message = f"{type(exc).__name__}: {exc}"
        return CheckResult(False, None, round(elapsed, 1), message[:300])
