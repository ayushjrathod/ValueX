import json
import logging
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from src.config.settings import (
    TOP_HOLDINGS_COUNT,
    get_settings,
)
from src.tools.market_data import TOOL_FUNCTIONS, TOOL_SCHEMAS
from src.tools.metrics import (
    compute_benchmark_comparison,
    compute_concentration,
    compute_performance,
)

logger = logging.getLogger(__name__)

def _accum_usage(
    response: object, inp: int, out: int,
) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage:
        inp += getattr(usage, "input_tokens", 0)
        out += getattr(usage, "output_tokens", 0)
    return inp, out


TOOL_FETCH_PROMPT = """\
You are Valura's market-data fetcher for portfolio health checks.
Your ONLY job is to call the right tools to gather data. Do NOT analyse it.

RULES:
1. Broad health check ("how is my portfolio?"):
   → get_current_prices with ALL portfolio tickers
   → get_benchmark_return with the user's preferred benchmark, period "1y"
   → Make BOTH calls in the SAME round.

2. Focused follow-up about specific tickers ("tell me about AAPL"):
   → get_current_prices with ONLY those tickers.
   → If the question is about concentration or diversification, fetch ALL tickers.
   → Call get_benchmark_return if benchmark comparison is relevant.

3. Skip fetches when conversation history already has the data.

4. After calling tools, reply briefly — analysis is handled separately.\
"""

OBSERVATION_PROMPT = """\
You are Valura's Portfolio Health Check agent. You speak to novice investors in
plain, jargon-free language.

You are given fixed portfolio metrics from the server. Write
1-5 plain-language observations about what matters most.

Rules:
- "warning" severity for risks and problems.
- "info" severity for positive or neutral findings.
- Each observation is 1-2 sentences max.
- Reference specific numbers from the computed metrics.
- For focused follow-ups, emphasise the requested ticker(s).
- Never guarantee returns or make predictions.
- Use the user's base currency for monetary references.
- If the portfolio is empty, suggest diversified low-cost index funds.\
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
) -> dict[str, Any]:
    settings = get_settings()
    model_name = model or settings.openai_model
    positions = user.get("positions", []) if user else []

    if not positions:
        return _handle_empty_portfolio(user, query, client, model_name, history)

    fetched_prices, fetched_currencies, benchmark_data, fetch_in, fetch_out = _fetch_market_data(
        user, query, client, model_name, history, positions,
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
        "input_tokens": fetch_in + obs_in,
        "output_tokens": fetch_out + obs_out,
    }
    return result


def _fetch_market_data(
    user: dict[str, Any] | None,
    query: str | None,
    client: OpenAI,
    model_name: str,
    history: list[dict[str, str]] | None,
    positions: list[dict[str, Any]],
) -> tuple[dict[str, float], dict[str, str], dict[str, Any] | None, int, int]:
    user_context = _build_tool_context(user, positions)

    input_items: list[Any] = [
        {"role": "system", "content": TOOL_FETCH_PROMPT},
    ]
    if history:
        input_items.extend(history)

    user_msg = user_context
    if query:
        user_msg = f"User query: {query}\n\n{user_context}"
    input_items.append({"role": "user", "content": user_msg})

    fetched_prices: dict[str, float] = {}
    fetched_currencies: dict[str, str] = {}
    benchmark_data: dict[str, Any] | None = None
    inp_tok, out_tok = 0, 0
    settings = get_settings()
    tool_cache: dict[tuple[str, str], str] = {}

    for round_num in range(settings.portfolio_max_tool_rounds):
        response = client.responses.create(
            model=model_name,
            input=input_items,
            tools=TOOL_SCHEMAS,
            store=False,
            temperature=settings.portfolio_tool_temperature,
        )
        inp_tok, out_tok = _accum_usage(response, inp_tok, out_tok)

        tool_calls = [
            item
            for item in response.output
            if getattr(item, "type", None) == "function_call"
        ]
        if not tool_calls:
            break

        logger.info("Agent round %d: %d tool call(s)", round_num + 1, len(tool_calls))

        for item in response.output:
            input_items.append(item)

        for call in tool_calls:
            cache_key = (call.name, call.arguments)
            if cache_key in tool_cache:
                tool_result = tool_cache[cache_key]
                logger.debug("Tool dedup hit: %s", call.name)
            else:
                tool_result = _execute_tool(call.name, call.arguments)
                tool_cache[cache_key] = tool_result
            logger.info("Tool %s -> %s", call.name, tool_result[:200])
            input_items.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": tool_result,
            })

            parsed = json.loads(tool_result)
            if call.name == "get_current_prices":
                for ticker, info in parsed.items():
                    if isinstance(info, dict) and "price" in info:
                        fetched_prices[ticker] = info["price"]
                        fetched_currencies[ticker] = info.get("currency", "USD")
            elif call.name == "get_benchmark_return" and "error" not in parsed:
                benchmark_data = parsed
    else:
        logger.warning("Tool loop exhausted %d rounds", settings.portfolio_max_tool_rounds)

    return fetched_prices, fetched_currencies, benchmark_data, inp_tok, out_tok


# Observation generation


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

    input_items: list[Any] = [
        {"role": "system", "content": OBSERVATION_PROMPT},
    ]
    if history:
        prior = [m["content"] for m in history if m.get("role") == "user"]
        if prior:
            ctx = "Recent conversation:\n" + "\n".join(
                f"- {q}" for q in prior[-settings.portfolio_recent_history_turns:]
            )
            input_items.append({"role": "user", "content": ctx})
            input_items.append({"role": "assistant", "content": "Understood."})

    msg = f"User query: {query or 'portfolio health check'}\n\n{user_brief}\n\n{metrics_block}"
    input_items.append({"role": "user", "content": msg})

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


def _build_tool_context(
    user: dict[str, Any] | None,
    positions: list[dict[str, Any]],
) -> str:
    if user is None:
        return "No user profile linked."

    tickers = [p["ticker"] for p in positions]
    benchmark = user.get("preferences", {}).get("preferred_benchmark", "S&P 500")

    return (
        f"User: {user.get('name', 'Unknown')}, "
        f"Country: {user.get('country', 'N/A')}, "
        f"Base currency: {user.get('base_currency', 'USD')}.\n"
        f"Preferred benchmark: {benchmark}\n"
        f"Portfolio tickers ({len(tickers)}): {', '.join(tickers)}"
    )


def _build_user_brief(user: dict[str, Any] | None) -> str:
    if user is None:
        return "User: Unknown (no profile linked)"
    return (
        f"User: {user.get('name', 'Unknown')}, Age: {user.get('age', 'N/A')}, "
        f"Country: {user.get('country', 'N/A')}, "
        f"Risk profile: {user.get('risk_profile', 'N/A')}, "
        f"Base currency: {user.get('base_currency', 'USD')}."
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
    lines = ["=== METRICS (authoritative; stick to these figures) ===\n"]

    if not positions:
        lines.append("Portfolio: EMPTY — no positions held.")
        return "\n".join(lines)

    lines.append("Holdings (current market data):")
    for p in positions:
        ticker = p["ticker"]
        qty = p["quantity"]
        cost = p["avg_cost"]
        price = fetched_prices.get(ticker)
        ccy = (fetched_currencies or {}).get(ticker) or p.get("currency", "USD")
        if price is not None:
            ret = ((price - cost) / cost) * 100.0
            current_val = qty * price
            cost_val = qty * cost
            lines.append(
                f"  {ticker}: {qty} shares, cost {cost:.2f} {ccy}, "
                f"current {price:.2f} {ccy} ({ret:+.1f}%), "
                f"value {current_val:,.0f} {ccy} (cost basis {cost_val:,.0f} {ccy})"
            )
        else:
            lines.append(f"  {ticker}: {qty} shares, cost {cost:.2f} {ccy}, current price unavailable")

    if focus_tickers:
        lines.append(f"\nFocused analysis on: {', '.join(focus_tickers)}")

    if concentration:
        top = concentration.get("top_ticker", "unknown")
        lines.append(f"\nConcentration Risk (by current market value):")
        lines.append(f"  Largest position ({top}): {concentration['top_position_pct']}%")
        lines.append(f"  Top {TOP_HOLDINGS_COUNT} positions: {concentration['top_3_positions_pct']}%")
        lines.append(f"  Flag: {concentration['flag']}")
        if concentration.get("notes"):
            lines.append(f"  Note: {concentration['notes']}")

    if performance:
        scope = f"for {', '.join(focus_tickers)}" if focus_tickers else "overall"
        lines.append(f"\nPerformance ({scope}):")
        lines.append(f"  Total return: {performance['total_return_pct']}%")
        if performance.get("annualized_return_pct") is not None:
            lines.append(f"  Annualized return: {performance['annualized_return_pct']}%")
        if performance.get("notes"):
            lines.append(f"  Note: {performance['notes']}")

    if benchmark_comparison:
        lines.append(f"\nBenchmark Comparison:")
        lines.append(f"  Benchmark: {benchmark_comparison['benchmark']}")
        lines.append(f"  Benchmark return: {benchmark_comparison['benchmark_return_pct']}%")
        lines.append(f"  Portfolio return: {benchmark_comparison['portfolio_return_pct']}%")
        lines.append(f"  Alpha: {benchmark_comparison['alpha_pct']}%")

    return "\n".join(lines)


def _execute_tool(name: str, arguments: str) -> str:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        args = json.loads(arguments)
        return func(**args)
    except Exception as exc:
        logger.warning("Tool execution error for %s: %s", name, exc)
        return json.dumps({"error": f"Tool {name} failed: {str(exc)}"})


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
