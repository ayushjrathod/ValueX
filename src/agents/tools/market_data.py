"""Market data helpers powered by yfinance."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import yfinance as yf

from src.config.settings import get_settings
from src.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)


# Defensible TTLs for a "health check" product:
# - Positive: 300s — yfinance free-tier `info` is already ~15min delayed,
#   so 5 minutes of additional staleness is well within the noise floor.
# - Negative: 30s — never cache a transient yfinance error for 5 minutes,
#   but don't hammer yfinance every request on a flapping ticker either.
_POSITIVE_TTL_S = 300.0
_NEGATIVE_TTL_S = 30.0

_PRICE_CACHE = TTLCache(_POSITIVE_TTL_S, _NEGATIVE_TTL_S)
_BENCHMARK_CACHE = TTLCache(_POSITIVE_TTL_S, _NEGATIVE_TTL_S)


def clear_market_data_cache() -> None:
    """Reset both caches. Test fixtures call this to keep runs isolated."""
    _PRICE_CACHE.clear()
    _BENCHMARK_CACHE.clear()


# Native fetchers  -----------------------------------------------------------

def _fetch_single_price(ticker: str) -> dict[str, Any]:
    cached = _PRICE_CACHE.get(ticker)
    if cached is not None:
        return cached
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None:
            payload = {"ticker": ticker, "error": f"No price data available for {ticker}"}
            _PRICE_CACHE.set(ticker, payload, is_error=True)
            return payload
        payload = {
            "ticker": ticker,
            "price": round(float(price), 2),
            "currency": info.get("currency", "USD"),
            "market_cap": info.get("marketCap"),
            "name": info.get("shortName", ticker),
        }
        _PRICE_CACHE.set(ticker, payload)
        return payload
    except Exception as exc:
        logger.warning("yfinance error for %s: %s", ticker, exc)
        payload = {"ticker": ticker, "error": str(exc)}
        _PRICE_CACHE.set(ticker, payload, is_error=True)
        return payload


def fetch_prices(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch current prices for *tickers* in parallel. Returns dict keyed by ticker."""
    if not tickers:
        return {}
    workers = min(len(tickers), get_settings().market_data_max_workers)
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_single_price, t): t for t in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            results[ticker] = future.result()
    return results


def fetch_benchmark(symbol: str, period: str) -> dict[str, Any]:
    """Fetch benchmark return over *period* (e.g. "1y"). Returns dict; cache-backed."""
    key = (symbol, period)
    cached = _BENCHMARK_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        hist = yf.Ticker(symbol).history(period=period)
        if hist.empty:
            payload = {"error": f"No data for {symbol} over {period}"}
            _BENCHMARK_CACHE.set(key, payload, is_error=True)
            return payload
        start_price = float(hist["Close"].iloc[0])
        end_price = float(hist["Close"].iloc[-1])
        return_pct = ((end_price - start_price) / start_price) * 100.0
        payload = {
            "symbol": symbol,
            "period": period,
            "start_price": round(start_price, 2),
            "end_price": round(end_price, 2),
            "return_pct": round(return_pct, 2),
            "data_points": len(hist),
        }
        _BENCHMARK_CACHE.set(key, payload)
        return payload
    except Exception as exc:
        logger.warning("yfinance benchmark error for %s: %s", symbol, exc)
        payload = {"error": f"Failed to fetch benchmark data: {str(exc)}"}
        _BENCHMARK_CACHE.set(key, payload, is_error=True)
        return payload


