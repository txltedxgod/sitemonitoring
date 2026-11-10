"""Integration tests for dashboard, site CRUD validation, manual check-now, and health."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import database, main, scheduler
from app.models import Base
from app.services import checker, telegram
from app.services.checker import CheckResult


@pytest.fixture()
def monitor_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    db_file = tmp_path / "monitor_test.db"
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}", echo=False, future=True
    )
    test_session_maker = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )

    monkeypatch.setattr(main.settings, "database_url", f"sqlite+aiosqlite:///{db_file.as_posix()}")
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "async_session", test_session_maker)
    monkeypatch.setattr(scheduler, "start_scheduler", lambda: None)
    monkeypatch.setattr(scheduler, "shutdown_scheduler", lambda: None)
    monkeypatch.setattr(main, "start_scheduler", lambda: None)
    monkeypatch.setattr(main, "shutdown_scheduler", lambda: None)

    async def test_init_db() -> None:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(main, "init_db", test_init_db)

    async def fake_check(*args, **kwargs) -> CheckResult:
        return CheckResult(True, 200, 21.5, None)

    async def fake_send(*args, **kwargs) -> bool:
        return True

    monkeypatch.setattr(checker, "check_site", fake_check)
    monkeypatch.setattr(telegram, "send_message", fake_send)

    app = main.create_app()
    with TestClient(app) as client:
        yield client


def test_health_and_dashboard(monitor_client: TestClient) -> None:
    health = monitor_client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    dash = monitor_client.get("/")
    assert dash.status_code == 200


def test_site_validation_and_lifecycle(monitor_client: TestClient) -> None:
    bad = monitor_client.post(
        "/sites",
        data={"name": "Bad", "url": "ftp://invalid.local", "interval_minutes": 5},
        follow_redirects=False,
    )
    assert bad.status_code == 303
    assert "error=" in bad.headers["location"]

    created = monitor_client.post(
        "/sites",
        data={
            "name": "Example Site",
            "url": "https://example.com",
            "interval_minutes": 5,
            "expected_status": "200",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert created.headers["location"] == "/"

    recheck = monitor_client.post("/sites/1/check-now", follow_redirects=False)
    assert recheck.status_code == 303
    assert recheck.headers["location"] == "/sites/1"

    detail = monitor_client.get("/sites/1")
    assert detail.status_code == 200
    assert "Example Site" in detail.text

    deleted = monitor_client.post("/sites/1/delete", follow_redirects=False)
    assert deleted.status_code == 303
    missing = monitor_client.get("/sites/1", follow_redirects=False)
    assert missing.status_code == 303
    assert missing.headers["location"] == "/"
