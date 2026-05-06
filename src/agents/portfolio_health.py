import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from src.config.settings import (
    TOP_HOLDINGS_COUNT,
    get_settings,
)
from src.tools.market_data import fetch_benchmark, fetch_prices
from src.tools.metrics import (
    compute_benchmark_comparison,
    compute_concentration,
    compute_performance,
)

logger = logging.getLogger(__name__)


# Benchmark mapping 
#
# The classifier extracts an optional `index` entity ("S&P 500", "NASDAQ", ...)
# and the user fixture stores `preferences.preferred_benchmark` in similar
# human-friendly form. yfinance needs an ETF/symbol. Map names → symbols here
# rather than having the LLM translate.

_BENCHMARK_SYMBOLS: dict[str, str] = {
    "S&P 500": "SPY",
    "S&P500": "SPY",
    "SP500": "SPY",
    "SPX": "SPY",
    "SPY": "SPY",
    "NASDAQ": "QQQ",
    "NASDAQ 100": "QQQ",
    "NASDAQ-100": "QQQ",
    "NASDAQ COMPOSITE": "QQQ",
    "QQQ": "QQQ",
    "FTSE": "ISF.L",
    "FTSE 100": "ISF.L",
    "RUSSELL 2000": "IWM",
    "IWM": "IWM",
    "MSCI WORLD": "URTH",
    "URTH": "URTH",
    "NIKKEI": "1321.T",
    "NIKKEI 225": "1321.T",
    "DOW": "DIA",
    "DOW JONES": "DIA",
    "DJIA": "DIA",
}


def _benchmark_symbol(name: str | None) -> str | None:
    if not name:
        return None
    key = name.upper().strip()
    return _BENCHMARK_SYMBOLS.get(key, name)


OBSERVATION_PROMPT = """\
ValueX Portfolio Health agent. Audience: novice investors. Plain language, no jargon.

Given fixed metrics, write 1-5 short observations on what matters most.
- severity: "warning" for risks, "info" for neutral/positive
- 1-2 sentences each; cite specific numbers from the metrics
- focus_tickers (when set) take priority
- never guarantee returns or predict
- use the user's base currency
- empty portfolio: suggest diversified low-cost index funds\
"""

_DISCLAIMER = (
    "This is not investment advice. Past performance does not guarantee future results. "
    "Please consult a qualified financial advisor before making investment decisions."
)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Literal["warning", "info"] = Field(
        ..., description="warning for risks, info for neutral/positive."
    )
    text: str = Field(..., description="Plain-language observation, 1-2 sentences.")


class ObservationsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[Observation] = Field(
        ..., description="1-5 actionable observations ordered by importance."
    )


class PortfolioHealthError(RuntimeError):
    pass


def run(
    user: dict[str, Any] | None = None,
    *,
    query: str | None = None,
    client: OpenAI,
    model: str | None = None,
    history: list[dict[str, str]] | None = None,
    focus_tickers: list[str] | None = None,
    benchmark_hint: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    model_name = model or settings.openai_model
    positions = user.get("positions", []) if user else []

    if not positions:
        return _handle_empty_portfolio(user, query, client, model_name, history)

    fetched_prices, fetched_currencies, benchmark_data = _prefetch_market_data(
        user, positions, focus_tickers, benchmark_hint,
    )

    concentration = compute_concentration(positions, fetched_prices, currency_map=fetched_currencies)
    performance = compute_performance(positions, fetched_prices, focus_tickers, currency_map=fetched_currencies)

    benchmark_comparison = None
    if performance and benchmark_data:
        benchmark_comparison = compute_benchmark_comparison(
            performance["total_return_pct"], benchmark_data,
        )

    observations, obs_in, obs_out = _generate_observations(
        user, query, client, model_name, history,
        positions, fetched_prices,
        concentration, performance, benchmark_comparison,
        focus_tickers, fetched_currencies,
    )

    result: dict[str, Any] = {}
    if concentration:
        result["concentration_risk"] = {
            k: v for k, v in concentration.items() if k != "top_ticker"
        }
    if performance:
        result["performance"] = performance
    if benchmark_comparison:
        result["benchmark_comparison"] = benchmark_comparison
    result["observations"] = observations
    result["status"] = "ok"
    result["agent"] = "portfolio_health"
    result["disclaimer"] = _DISCLAIMER
    result["_meta"] = {
        "input_tokens": obs_in,
        "output_tokens": obs_out,
    }
    return result


def _prefetch_market_data(
    user: dict[str, Any] | None,
    positions: list[dict[str, Any]],
    focus_tickers: list[str] | None,
    benchmark_hint: str | None,
) -> tuple[dict[str, float], dict[str, str], dict[str, Any] | None]:
    """Run price + benchmark fetches in parallel.

    The LLM does not need to "decide" what to fetch — the classifier already
    extracted any focus tickers / benchmark hints, and the user's preferred
    benchmark is in their profile. Skip the tool-calling round-trip entirely.
    """
    tickers = list(focus_tickers) if focus_tickers else [p["ticker"] for p in positions]

    user_pref = (user or {}).get("preferences", {}).get("preferred_benchmark")
    benchmark = _benchmark_symbol(benchmark_hint) or _benchmark_symbol(user_pref)

    fetched_prices: dict[str, float] = {}
    fetched_currencies: dict[str, str] = {}
    benchmark_data: dict[str, Any] | None = None

    with ThreadPoolExecutor(max_workers=2) as pool:
        prices_future = pool.submit(fetch_prices, tickers)
        bench_future = pool.submit(fetch_benchmark, benchmark, "1y") if benchmark else None

        prices_result = prices_future.result()
        for ticker, info in prices_result.items():
            if isinstance(info, dict) and "price" in info:
                fetched_prices[ticker] = info["price"]
                fetched_currencies[ticker] = info.get("currency", "USD")

        if bench_future is not None:
            bench_result = bench_future.result()
            if "error" not in bench_result:
                benchmark_data = bench_result
            else:
                logger.info("Benchmark fetch failed for %s: %s", benchmark, bench_result["error"])

    return fetched_prices, fetched_currencies, benchmark_data


# Observation generation  ----------------------------------------------------


def _generate_observations(
    user: dict[str, Any] | None,
    query: str | None,
    client: OpenAI,
    model_name: str,
    history: list[dict[str, str]] | None,
    positions: list[dict[str, Any]],
    fetched_prices: dict[str, float],
    concentration: dict[str, Any] | None,
    performance: dict[str, Any] | None,
    benchmark_comparison: dict[str, Any] | None,
    focus_tickers: list[str] | None,
    fetched_currencies: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    metrics_block = _format_metrics_for_llm(
        positions, fetched_prices,
        concentration, performance, benchmark_comparison,
        focus_tickers,
        fetched_currencies=fetched_currencies,
    )
    user_brief = _build_user_brief(user)
    settings = get_settings()

    parts: list[str] = []
    if history:
        prior = [m["content"] for m in history if m.get("role") == "user"]
        if prior:
            recent = prior[-settings.portfolio_recent_history_turns:]
            parts.append("recent: " + " | ".join(recent))
    parts.append(f"query: {query or 'portfolio health check'}")
    parts.append(user_brief)
    parts.append(metrics_block)

    input_items: list[Any] = [
        {"role": "system", "content": OBSERVATION_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]

    response = client.responses.parse(
        model=model_name,
        input=input_items,
        store=False,
        temperature=settings.portfolio_observation_temperature,
        text_format=ObservationsResult,
    )
    inp_tok, out_tok = _accum_usage(response, 0, 0)

    parsed = _parse_observations(response)
    return [obs.model_dump() for obs in parsed.observations], inp_tok, out_tok


def _accum_usage(
    response: object, inp: int, out: int,
) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage:
        inp += getattr(usage, "input_tokens", 0)
        out += getattr(usage, "output_tokens", 0)
    return inp, out


def _handle_empty_portfolio(
    user: dict[str, Any] | None,
    query: str | None,
    client: OpenAI,
    model_name: str,
    history: list[dict[str, str]] | None,
) -> dict[str, Any]:
    observations, inp_tok, out_tok = _generate_observations(
        user, query, client, model_name, history,
        positions=[], fetched_prices={},
        concentration=None, performance=None,
        benchmark_comparison=None, focus_tickers=None,
    )
    return {
        "observations": observations,
        "status": "ok",
        "agent": "portfolio_health",
        "disclaimer": _DISCLAIMER,
        "_meta": {"input_tokens": inp_tok, "output_tokens": out_tok},
    }


def _build_user_brief(user: dict[str, Any] | None) -> str:
    if user is None:
        return "user: unknown"
    return (
        f"user: {user.get('name', 'Unknown')} | age {user.get('age', 'N/A')} | "
        f"{user.get('country', 'N/A')} | risk={user.get('risk_profile', 'N/A')} | "
        f"base_ccy={user.get('base_currency', 'USD')}"
    )


def _format_metrics_for_llm(
    positions: list[dict[str, Any]],
    fetched_prices: dict[str, float],
    concentration: dict[str, Any] | None,
    performance: dict[str, Any] | None,
    benchmark_comparison: dict[str, Any] | None,
    focus_tickers: list[str] | None,
    fetched_currencies: dict[str, str] | None = None,
) -> str:
    lines = ["METRICS (authoritative — stick to these numbers):"]

    if not positions:
        lines.append("portfolio: EMPTY")
        return "\n".join(lines)

    lines.append("holdings:")
    for p in positions:
        ticker = p["ticker"]
        qty = p["quantity"]
        cost = p["avg_cost"]
        price = fetched_prices.get(ticker)
        ccy = (fetched_currencies or {}).get(ticker) or p.get("currency", "USD")
        if price is not None:
            ret = ((price - cost) / cost) * 100.0
            lines.append(
                f"  {ticker} qty={qty} cost={cost:.2f} px={price:.2f} ret={ret:+.1f}% {ccy}"
            )
        else:
            lines.append(f"  {ticker} qty={qty} cost={cost:.2f} {ccy} (no live price)")

    if focus_tickers:
        lines.append(f"focus: {', '.join(focus_tickers)}")

    if concentration:
        top = concentration.get("top_ticker", "?")
        notes = f" | {concentration['notes']}" if concentration.get("notes") else ""
        lines.append(
            f"concentration: top={top} {concentration['top_position_pct']}% / "
            f"top{TOP_HOLDINGS_COUNT}={concentration['top_3_positions_pct']}% / "
            f"flag={concentration['flag']}{notes}"
        )

    if performance:
        scope = "/".join(focus_tickers) if focus_tickers else "overall"
        ann = performance.get("annualized_return_pct")
        ann_str = f" annualized={ann}%" if ann is not None else ""
        notes = f" | {performance['notes']}" if performance.get("notes") else ""
        lines.append(
            f"performance ({scope}): total={performance['total_return_pct']}%{ann_str}{notes}"
        )

    if benchmark_comparison:
        lines.append(
            f"benchmark: {benchmark_comparison['benchmark']} "
            f"bench={benchmark_comparison['benchmark_return_pct']}% "
            f"port={benchmark_comparison['portfolio_return_pct']}% "
            f"alpha={benchmark_comparison['alpha_pct']}%"
        )

    return "\n".join(lines)


def _parse_observations(response: object) -> ObservationsResult:
    parsed = getattr(response, "output_parsed", None)
    if parsed is not None:
        return ObservationsResult.model_validate(parsed)

    for output in getattr(response, "output", []):
        if getattr(output, "type", None) != "message":
            continue
        for item in getattr(output, "content", []):
            if getattr(item, "type", None) == "refusal":
                raise PortfolioHealthError(
                    getattr(item, "refusal", "LLM refused to produce observations.")
                )
            parsed = getattr(item, "parsed", None)
            if parsed is not None:
                return ObservationsResult.model_validate(parsed)

    logger.warning("Could not parse observations from LLM response, using fallback")
    return ObservationsResult(
        observations=[
            Observation(severity="info", text="Unable to generate specific observations. Please try again."),
        ]
    )
