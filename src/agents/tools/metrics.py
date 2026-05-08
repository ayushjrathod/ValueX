"""Deterministic portfolio math (concentration, performance, vs benchmark)."""

import math
from datetime import date, datetime
from typing import Any

from src.config.settings import (
    HIGH_CONCENTRATION_THRESHOLD_PCT,
    TOP_HOLDINGS_COUNT,
    WARN_CONCENTRATION_THRESHOLD_PCT,
)


def compute_concentration(
    positions: list[dict[str, Any]],
    price_map: dict[str, float],
    currency_map: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Largest and top-N weights using live prices, falling back to cost basis."""
    if not positions:
        return None

    market_values: list[tuple[str, float]] = []
    for p in positions:
        ticker = p["ticker"]
        qty = p["quantity"]
        price = price_map.get(ticker, p["avg_cost"])
        market_values.append((ticker, qty * price))

    total = sum(v for _, v in market_values)
    if total <= 0:
        return None

    market_values.sort(key=lambda x: x[1], reverse=True)

    top_pct = round(
        market_values[0][1] / total * 100.0,
        1,
    )
    top3 = round(
        sum(v for _, v in market_values[:TOP_HOLDINGS_COUNT]) / total * 100.0,
        1,
    )
    flag = (
        "high"
        if top_pct > HIGH_CONCENTRATION_THRESHOLD_PCT
        else ("warning" if top_pct > WARN_CONCENTRATION_THRESHOLD_PCT else "low")
    )

    notes = None
    currencies = {currency_map.get(p["ticker"], p.get("currency", "USD")) for p in positions} if currency_map else {p.get("currency", "USD") for p in positions}
    if len(currencies) > 1:
        notes = "Multi-currency portfolio; values shown in position currencies without FX conversion. Concentration is approximate."

    return {
        "top_position_pct": top_pct,
        "top_3_positions_pct": top3,
        "flag": flag,
        "top_ticker": market_values[0][0],
        "notes": notes,
    }


def compute_performance(
    positions: list[dict[str, Any]],
    price_map: dict[str, float],
    focus_tickers: list[str] | None = None,
    currency_map: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Simple P/L and optional CAGR; *focus_tickers* limits which rows count."""
    if not positions:
        return None

    target = (
        [p for p in positions if p["ticker"] in focus_tickers]
        if focus_tickers
        else positions
    )
    if not target:
        return None

    total_cost = 0.0
    total_current = 0.0
    earliest: date | None = None
    missing: list[str] = []

    for p in target:
        ticker = p["ticker"]
        price = price_map.get(ticker)
        if price is None:
            missing.append(ticker)
            continue
        qty = p["quantity"]
        total_cost += qty * p["avg_cost"]
        total_current += qty * price

        pa = p.get("purchased_at")
        if pa:
            try:
                d = datetime.strptime(pa, "%Y-%m-%d").date()
                if earliest is None or d < earliest:
                    earliest = d
            except ValueError:
                pass

    if total_cost <= 0:
        return None

    total_return_pct = round(
        (total_current - total_cost) / total_cost * 100.0,
        2,
    )

    annualized = None
    if earliest:
        years = (date.today() - earliest).days / 365.25
        if years >= 0.1:
            g = total_current / total_cost
            if g > 0:
                annualized = round(
                    (math.pow(g, 1.0 / years) - 1) * 100.0,
                    2,
                )

    notes = None
    if missing:
        notes = f"Live prices unavailable for {', '.join(missing)}; excluded from calculation."

    currencies = {currency_map.get(p["ticker"], p.get("currency", "USD")) for p in target} if currency_map else {p.get("currency", "USD") for p in target}
    if len(currencies) > 1:
        currency_warning = "Multi-currency portfolio; returns are approximate without FX conversion."
        notes = f"{notes} {currency_warning}" if notes else currency_warning

    return {
        "total_return_pct": total_return_pct,
        "annualized_return_pct": annualized,
        "notes": notes,
    }


def compute_benchmark_comparison(
    portfolio_return_pct: float,
    benchmark_data: dict[str, Any],
) -> dict[str, Any] | None:
    """Portfolio return minus benchmark return from the tool JSON."""
    if not benchmark_data or "error" in benchmark_data:
        return None

    bench_return = benchmark_data.get("return_pct")
    if bench_return is None:
        return None

    return {
        "benchmark": benchmark_data.get("symbol", "Unknown"),
        "portfolio_return_pct": portfolio_return_pct,
        "benchmark_return_pct": bench_return,
        "alpha_pct": round(portfolio_return_pct - bench_return, 2),
        "notes": None,
    }
