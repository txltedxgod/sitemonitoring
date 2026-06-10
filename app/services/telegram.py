"""Telegram notification helper (uses the Bot API directly via httpx)."""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger("monitor.telegram")


async def send_message(text: str) -> bool:
    if not settings.telegram_enabled:
        logger.info("Telegram disabled; skipping notification")
        return False
    base = "https://api.telegram.org/bot"
    api_url = base + settings.telegram_bot_token + "/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(api_url, json=payload)
        if resp.is_success:
            return True
        logger.warning(
            "Telegram API error %s: %s", resp.status_code, resp.text[:200]
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram send failed: %s", exc)
        return False
