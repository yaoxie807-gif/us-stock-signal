"""Telegram 手机推送，失败只记日志。"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

_ERROR_LOG = Path("logs/notify_errors.log")


def _log_error(exc: Exception) -> None:
    try:
        _ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _ERROR_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} {type(exc).__name__}: {exc}\n")
    except Exception:
        pass


def notify(title: str, body: str, priority: str = "default") -> bool:
    delivered = False
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": f"*{title}*\n{body}",
                    "parse_mode": "Markdown",
                },
                timeout=5,
            )
            response.raise_for_status()
            delivered = True
        except Exception as exc:
            _log_error(exc)

    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        _log_error(RuntimeError("no notification channel configured"))
    return delivered
