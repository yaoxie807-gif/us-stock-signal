"""从美股机器人抽取的纯函数：交易时段判断、仓位/止损、盘中量折算、选股筛选。

全部只用 yfinance 免费数据，不依赖 IBKR，可在 GitHub Actions 云端直接运行。
"""
from __future__ import annotations

import math
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

ET = ZoneInfo("America/New_York")

PHASE_WEEKEND = "weekend"
PHASE_TOO_EARLY = "too_early"
PHASE_CLOSED = "closed"
PHASE_MANAGE_ONLY = "manage_only"
PHASE_FORCE_CLOSE = "force_close"
PHASE_OK = "ok"


def market_phase(now_et: datetime) -> str:
    """按美东时间划分交易阶段；PHASE_OK 约为 10:05–15:30 的入场窗口。"""
    if now_et.weekday() >= 5:
        return PHASE_WEEKEND
    hm = now_et.hour * 60 + now_et.minute
    if hm < 10 * 60:
        return PHASE_TOO_EARLY
    if hm >= 16 * 60:
        return PHASE_CLOSED
    if 10 * 60 <= hm < 10 * 60 + 5:
        return PHASE_MANAGE_ONLY
    if 15 * 60 + 30 <= hm < 15 * 60 + 51:
        return PHASE_MANAGE_ONLY
    if 15 * 60 + 51 <= hm < 16 * 60:
        return PHASE_FORCE_CLOSE
    return PHASE_OK


def position_size(portfolio_value: float, risk_pct: float, price: float, stop: float,
                  max_position_pct: float = 10.0, max_trade_usd: float | None = None) -> int:
    r = price - stop
    if r <= 0 or price <= 0:
        return 0
    risk_dollars = portfolio_value * (risk_pct / 100.0)
    size = min(
        math.floor(risk_dollars / r),
        math.floor(portfolio_value * (max_position_pct / 100.0) / price),
    )
    if max_trade_usd is not None:
        size = min(size, math.floor(max_trade_usd / price))
    return max(size, 0)


def initial_stop_from_lod(low_of_day: float) -> float:
    return round(low_of_day * 0.99, 2)


# --- 选股筛选（morning_prefilter 的核心：批量下载 + gap/相对量筛 top20）---

_VOLUME_CURVE = [(0, 0.04), (5, 0.08), (30, 0.20), (60, 0.28),
                 (120, 0.40), (240, 0.65), (390, 1.0)]


def expected_volume_fraction(minutes_since_open: float) -> float:
    m = max(0.0, min(390.0, minutes_since_open))
    for (m1, f1), (m2, f2) in zip(_VOLUME_CURVE, _VOLUME_CURVE[1:]):
        if m <= m2:
            return f1 + (f2 - f1) * (m - m1) / (m2 - m1)
    return 1.0


def _clock_volume_fraction() -> float:
    now = datetime.now(ET)
    minutes = (now.hour - 9) * 60 + now.minute - 30
    return max(expected_volume_fraction(minutes), 0.02)


def to_yahoo_symbol(sym: str) -> str:
    return sym.replace(" ", "-")


def screen(tickers: list[str], min_gap_pct: float = 3.0, min_price: float = 3.0,
           min_rv: float = 1.0, max_survivors: int = 20) -> list[dict]:
    """批量下载当日日线，筛出 gap≥min_gap%、相对量≥min_rv 的 top N（按相对量排序）。"""
    volume_fraction = _clock_volume_fraction()
    yahoo = [to_yahoo_symbol(t) for t in tickers]
    y2i = dict(zip(yahoo, tickers))
    bars = yf.download(tickers=" ".join(yahoo), period="1mo", interval="1d",
                       group_by="ticker", threads=5, progress=False, auto_adjust=True)
    if bars is None or bars.empty:
        print("ALERT: yfinance 批量下载为空", file=sys.stderr)
        return []

    survivors, failed = [], 0
    for yt in yahoo:
        try:
            tb = bars[yt]
            prev_close = tb.iloc[-2]["Close"]
            today_open = tb.iloc[-1]["Open"]
            today_close = tb.iloc[-1]["Close"]
            today_vol = tb.iloc[-1]["Volume"]
            if pd.isna(prev_close) or pd.isna(today_open) or pd.isna(today_close):
                failed += 1
                continue
            gap_pct = (today_close - prev_close) / prev_close * 100
            prior_vol = tb["Volume"].iloc[:-1].tail(20)
            avg_vol = float(prior_vol.mean()) if len(prior_vol) else 0.0
            rv = (float(today_vol) / (avg_vol * volume_fraction)
                  if avg_vol > 0 and not pd.isna(today_vol) else 0.0)
        except (KeyError, IndexError, ValueError):
            failed += 1
            continue
        if today_close < min_price or gap_pct < min_gap_pct or rv < min_rv:
            continue
        survivors.append({"ticker": y2i[yt], "gap_pct": round(float(gap_pct), 2),
                          "rv": round(rv, 2), "open": round(float(today_open), 2)})

    if tickers and failed / len(tickers) >= 0.30:
        print(f"ALERT: yfinance 失败率高 ({failed}/{len(tickers)})", file=sys.stderr)
    survivors.sort(key=lambda s: s["rv"], reverse=True)
    return survivors[:max_survivors]
