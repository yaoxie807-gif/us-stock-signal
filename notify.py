"""Telegram（主）+ ntfy（备）手机推送，fire-and-forget：失败只记日志，绝不影响交易逻辑。"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
NOTIFY_URL = os.environ.get("NOTIFY_URL", "")

_ERROR_LOG = Path("logs/notify_errors.log")


def _log_error(exc: Exception) -> None:
    try:
        _ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _ERROR_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} {type(exc).__name__}: {exc}\n")
    except Exception:
        pass


def notify(title: str, body: str, priority: str = "default") -> None:
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": f"*{title}*\n{body}",
                    "parse_mode": "Markdown",
                },
                timeout=5,
            )
        except Exception as exc:
            _log_error(exc)
    if NOTIFY_URL:
        try:
            requests.post(
                NOTIFY_URL,
                data=body.encode("utf-8"),
                headers={"Title": title, "Priority": priority},
                timeout=5,
            )
        except Exception as exc:
            _log_error(exc)
