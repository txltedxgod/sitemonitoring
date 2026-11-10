"""Unit tests for site health checker, Telegram HTML escaping, and alert state transitions."""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, Site
from app.services import checker, monitor, telegram
from app.services.checker import CheckResult


class _FakeAsyncClient:
    def __init__(self, *, status_code: int = 200, exc: Exception | None = None, **kwargs) -> None:
        self._status_code = status_code
        self._exc = exc

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get(self, url: str, headers: dict | None = None) -> httpx.Response:
        if self._exc is not None:
            raise self._exc
        return httpx.Response(self._status_code, request=httpx.Request("GET", url))


@pytest.mark.asyncio
async def test_check_site_handles_status_and_network_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        checker.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient(status_code=204, **kw)
    )
    ok = await checker.check_site("https://example.com")
    assert ok.is_up is True
    assert ok.status_code == 204

    mismatch = await checker.check_site("https://example.com", expected_status=200)
    assert mismatch.is_up is False
    assert mismatch.error == "Unexpected HTTP 204"

    monkeypatch.setattr(
        checker.httpx,
        "AsyncClient",
        lambda **kw: _FakeAsyncClient(exc=httpx.ConnectTimeout("timed out"), **kw),
    )
    down = await checker.check_site("https://example.com")
    assert down.is_up is False
    assert down.status_code is None
    assert "ConnectTimeout" in (down.error or "")


@pytest.mark.asyncio
async def test_check_single_alerts_only_on_state_transitions_and_escapes_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    sent_alerts: list[str] = []

    async def fake_send(msg: str) -> bool:
        sent_alerts.append(msg)
        return True

    monkeypatch.setattr(telegram, "send_message", fake_send)

    async with session_maker() as session:
        site = Site(
            name="Prod <API> & Edge",
            url="https://api.example.com",
            interval_minutes=5,
        )
        session.add(site)
        await session.flush()

        async def return_down(*args, **kwargs) -> CheckResult:
            return CheckResult(False, 503, 12.0, "HTTP <503> & down")

        monkeypatch.setattr(checker, "check_site", return_down)
        # Transition unknown -> down triggers DOWN alert
        await monitor.check_single(session, site)
        assert len(sent_alerts) == 1
        assert "Prod &lt;API&gt; &amp; Edge" in sent_alerts[0]
        assert "HTTP &lt;503&gt; &amp; down" in sent_alerts[0]

        # Staying down -> down does NOT re-alert
        await monitor.check_single(session, site)
        assert len(sent_alerts) == 1

        # Recovery down -> up triggers UP alert
        async def return_up(*args, **kwargs) -> CheckResult:
            return CheckResult(True, 200, 15.0, None)

        monkeypatch.setattr(checker, "check_site", return_up)
        await monitor.check_single(session, site)
        assert len(sent_alerts) == 2
        assert "is back UP" in sent_alerts[1]

    await engine.dispose()
