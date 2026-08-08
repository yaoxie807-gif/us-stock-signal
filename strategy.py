import json

import numpy as np


def load_rules(path: str = "rules.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_daily_filters(daily_bars, rules: dict) -> dict:
    filters = rules["daily_filters"]
    today = daily_bars.iloc[-1]
    prior = daily_bars.iloc[-2]
    sma200 = daily_bars["Close"].rolling(200).mean().iloc[-2]
    gap_pct = (today["Open"] - prior["Close"]) / prior["Close"] * 100

    checks = {}
    if filters.get("D1_above_prior_day_high"):
        checks["D1_above_prior_day_high"] = bool(today["Open"] > prior["High"])
    if filters.get("D2_prior_close_above_sma200"):
        checks["D2_prior_close_above_sma200"] = bool(prior["Close"] > sma200) if not np.isnan(sma200) else False
    if "D3_min_gap_pct_from_prior_close" in filters:
        checks["D3_min_gap_pct_from_prior_close"] = bool(gap_pct >= filters["D3_min_gap_pct_from_prior_close"])

    return {
        "passed": all(checks.values()) if checks else True,
        "checks": checks,
        "gap_pct": float(gap_pct),
    }


def evaluate_intraday_filters(intraday_bars, premarket_high: float, rules: dict) -> dict:
    filters = rules["intraday_filters"]
    latest = intraday_bars.iloc[-1]
    # High-of-day-so-far excludes the latest bar itself: a bar's own High is by
    # definition >= its own Close, so including it would make "latest Close >=
    # today_high" nearly impossible to satisfy on the very bar that sets a new high.
    prior_high = intraday_bars["High"].iloc[:-1].max()
    today_low = intraday_bars["Low"].min()

    checks = {}
    if filters.get("I1_above_premarket_high"):
        checks["I1_above_premarket_high"] = bool(latest["Close"] > premarket_high)
    if filters.get("I2_above_today_hod"):
        checks["I2_above_today_hod"] = bool(latest["Close"] >= prior_high)
    if "I3_rvol_min" in filters:
        # Simplified RVOL approximation: latest 5-minute bar volume divided by the mean
        # 5-minute bar volume over the trailing I3_rvol_lookback_days *bars* (not calendar
        # days) within the same DataFrame. This is not a true time-of-day-adjusted RVOL,
        # but is an accepted simplification for this default template strategy.
        lookback = filters.get("I3_rvol_lookback_days", 14)
        avg_volume = intraday_bars["Volume"].iloc[:-1].tail(lookback).mean()
        rvol = latest["Volume"] / avg_volume if avg_volume else 0.0
        checks["I3_rvol_min"] = bool(rvol >= filters["I3_rvol_min"])

    return {
        "passed": all(checks.values()) if checks else True,
        "checks": checks,
        "today_low": float(today_low),
    }


def evaluate_symbol(daily_bars, intraday_bars, premarket_high: float, rules: dict) -> dict:
    daily = evaluate_daily_filters(daily_bars, rules)
    intraday = evaluate_intraday_filters(intraday_bars, premarket_high, rules)
    return {
        "passed": daily["passed"] and intraday["passed"],
        "daily": daily,
        "intraday": intraday,
        "low_of_day": intraday["today_low"],
    }
