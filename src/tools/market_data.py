"""
Market data tools powered by yfinance.

These are registered as function tools for the OpenAI Responses API
agentic loop. Each function takes typed arguments and returns a JSON
string so the model can consume the results directly.
"""

import json
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import yfinance as yf

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


# Tool implementations

def _fetch_single_price(ticker: str) -> dict[str, Any]:
    """Fetch price data for one ticker. Returns a dict."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None:
            return {"ticker": ticker, "error": f"No price data available for {ticker}"}
        return {
            "ticker": ticker,
            "price": round(float(price), 2),
            "currency": info.get("currency", "USD"),
            "market_cap": info.get("marketCap"),
            "name": info.get("shortName", ticker),
        }
    except Exception as exc:
        logger.warning("yfinance error for %s: %s", ticker, exc)
        return {"ticker": ticker, "error": str(exc)}


def get_current_prices(tickers: list[str]) -> str:
    """Fetch current market prices for multiple tickers in parallel."""
    if not tickers:
        return json.dumps({})
    workers = min(len(tickers), get_settings().market_data_max_workers)
    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_single_price, t): t for t in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            results[ticker] = future.result()
    return json.dumps(results)


def get_benchmark_return(symbol: str, period: str) -> str:
    """Fetch the return of a benchmark index/ETF over *period*."""
    try:
        hist = yf.Ticker(symbol).history(period=period)
        if hist.empty:
            return json.dumps({"error": f"No data for {symbol} over {period}"})
        start_price = float(hist["Close"].iloc[0])
        end_price = float(hist["Close"].iloc[-1])
        return_pct = ((end_price - start_price) / start_price) * 100.0
        return json.dumps({
            "symbol": symbol,
            "period": period,
            "start_price": round(start_price, 2),
            "end_price": round(end_price, 2),
            "return_pct": round(return_pct, 2),
            "data_points": len(hist),
        })
    except Exception as exc:
        logger.warning("yfinance benchmark error for %s: %s", symbol, exc)
        return json.dumps({"error": f"Failed to fetch benchmark data: {str(exc)}"})


# Registry — maps tool name → callable

TOOL_FUNCTIONS: dict[str, Callable[..., str]] = {
    "get_current_prices": get_current_prices,
    "get_benchmark_return": get_benchmark_return,
}

# Responses API tool schemas 

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "get_current_prices",
        "description": (
            "Fetch current market prices for a list of stock tickers in one call. "
            "Returns price, currency, market cap, and company name per ticker. "
            "Use this to get live prices for all portfolio holdings at once."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of stock ticker symbols, e.g. ['AAPL', 'MSFT', 'NVDA']",
                },
            },
            "required": ["tickers"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_benchmark_return",
        "description": (
            "Fetch the return percentage for a benchmark index or ETF over a time "
            "period. Common benchmarks: SPY (S&P 500), QQQ (NASDAQ-100), "
            "IWM (Russell 2000), EFA (International Developed), AGG (US Bonds). "
            "Valid periods: 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Benchmark ETF/index ticker, e.g. SPY, QQQ",
                },
                "period": {
                    "type": "string",
                    "description": "Time period for return calculation, e.g. 1y, 6mo, ytd",
                },
            },
            "required": ["symbol", "period"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]
