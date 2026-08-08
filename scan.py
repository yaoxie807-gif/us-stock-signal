"""云端信号扫描：筛选当日在动的股 → 逐个按规则判断 → 有新信号发飞机。

一次运行 = 完整一轮，无需本地文件（适合 GitHub Actions 用完即弃的环境）。
只用 yfinance 免费数据，不碰 IBKR，不下单。去重靠 state/sent_<日期>.json：
同一只票当天首次触发才发，连续满足不重复刷屏；掉出后重新满足会再发。

用法:
    python scan.py            # 扫描并发飞机，更新去重记录
    python scan.py --dry-run  # 只打印，不发飞机、不写去重、跳过时段检查（测试用）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import yfinance as yf

import strategy
import helpers
from helpers import ET, PHASE_OK, initial_stop_from_lod, market_phase, position_size, screen
from notify import notify
from sp500_tickers import SP500_TICKERS

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

def _env_float(key: str, default: float) -> float:
    v = os.environ.get(key)
    return float(v) if v not in (None, "") else default


PORTFOLIO_VALUE = _env_float("PORTFOLIO_VALUE_USD", 25000)
MAX_TRADE_USD = _env_float("MAX_TRADE_SIZE_USD", 2500)
RISK_PCT = _env_float("MAX_RISK_PER_TRADE_PCT", 1.0)

STATE_DIR = Path("state")


def _state_file() -> Path:
    return STATE_DIR / f"sent_{datetime.now(ET).date().isoformat()}.json"


def load_sent() -> set[str]:
    f = _state_file()
    if not f.exists():
        return set()
    try:
        return set(json.loads(f.read_text(encoding="utf-8")).get("sent", []))
    except Exception:
        return set()


def save_sent(sent: set[str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_file().write_text(
        json.dumps({"date": datetime.now(ET).date().isoformat(), "sent": sorted(sent)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fetch_daily(symbol: str):
    df = yf.Ticker(symbol).history(period="1y", interval="1d", auto_adjust=False)
    return df if df is not None and not df.empty else None


def fetch_intraday(symbol: str):
    df = yf.Ticker(symbol).history(period="1d", interval="5m", prepost=True, auto_adjust=False)
    if df is None or df.empty:
        return None, None
    df.index = df.index.tz_convert(ET)
    rth = df.between_time("09:30", "15:59")
    pre = df.between_time("04:00", "09:29")
    premarket_high = float(pre["High"].max()) if not pre.empty else None
    return (rth if not rth.empty else None), premarket_high


def evaluate(symbol: str, rules: dict) -> dict | None:
    daily = fetch_daily(symbol)
    rth, premarket_high = fetch_intraday(symbol)
    if daily is None or rth is None or len(daily) < 2:
        return None
    if premarket_high is None:
        premarket_high = float(daily["Open"].iloc[-1])
    verdict = strategy.evaluate_symbol(daily, rth, premarket_high, rules)
    if not verdict["passed"]:
        return None
    price = float(rth["Close"].iloc[-1])
    stop = initial_stop_from_lod(verdict["low_of_day"])
    size = position_size(PORTFOLIO_VALUE, RISK_PCT, price, stop,
                         max_position_pct=10.0, max_trade_usd=MAX_TRADE_USD)
    if size < 1:
        return None
    entry_limit = round(price * 1.001, 2)
    return {"symbol": symbol, "entry_limit": entry_limit, "stop": stop, "size": size,
            "price": price, "risk_usd": round((entry_limit - stop) * size, 2)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    now = datetime.now(ET)
    if not args.dry_run and market_phase(now) != PHASE_OK:
        print(f"[{now:%Y-%m-%d %H:%M} ET] 非入场时段，跳过")
        return 0

    rules = strategy.load_rules()
    survivors = screen(SP500_TICKERS,
                       min_gap_pct=rules["daily_filters"].get("D3_min_gap_pct_from_prior_close", 3.0),
                       min_price=rules["universe_filters"].get("min_price_usd", 3.0),
                       min_rv=rules["intraday_filters"].get("I3_rvol_min", 1.0))
    print(f"[{now:%Y-%m-%d %H:%M} ET] 选股 {len(survivors)} 只: "
          + ", ".join(s["ticker"] for s in survivors))

    sent = load_sent()
    new_signals = 0
    for s in survivors:
        sym = s["ticker"]
        if sym in sent:
            continue  # 当天已发过，不重复刷屏
        try:
            sig = evaluate(sym, rules)
        except Exception as exc:
            print(f"  {sym}: 错误 {str(exc)[:100]}")
            continue
        if not sig:
            print(f"  - {sym}: 不符合")
            continue
        body = (f"买 {sig['symbol']}\n限价 {sig['entry_limit']}\n止损 {sig['stop']}\n"
                f"{sig['size']} 股（风险 ${sig['risk_usd']:.0f}）\n"
                f"现价 {sig['price']} · 数据 yfinance(约延迟15分) · 下单前核对券商实时价")
        print(f"  [信号] {sym}: 限价{sig['entry_limit']} 止损{sig['stop']} {sig['size']}股")
        if not args.dry_run:
            notify(f"📈 买入信号 {sym}", body, "high")
        sent.add(sym)
        new_signals += 1

    if new_signals and not args.dry_run:
        save_sent(sent)
    print(f"完成：新信号 {new_signals} 个 / 选股 {len(survivors)} 只")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
