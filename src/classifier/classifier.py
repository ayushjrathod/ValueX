import logging
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from src.agents.catalog import AgentName, render_agent_taxonomy
from src.config.settings import get_settings
from src.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)


# Process-wide dedupe for identical (query, session-context) pairs. The
# classifier is deterministic for a given input — repeating the LLM call
# burns ~3-4s and ~2k input tokens per duplicate. 5min TTL is far longer
# than any reasonable user think-time, but short enough that long-lived
# servers don't hold stale entries indefinitely.
_CLASSIFIER_CACHE_TTL_S = 300.0
_classifier_cache = TTLCache(_CLASSIFIER_CACHE_TTL_S, _CLASSIFIER_CACHE_TTL_S)


def clear_classifier_cache() -> None:
    """Reset the dedupe cache. Test fixtures call this for isolation."""
    _classifier_cache.clear()

CLASSIFIER_SYSTEM_PROMPT = """
You are Valura's financial intent classifier. Pick the single best agent,
write a 2-5 word intent label, extract only entities explicitly present
or strongly implied, and give an informational safety_verdict.

Use general_query for greetings, definitions, education, chatter, gibberish.
Use prior conversation (if given) to resolve follow-ups ("my portfolio", "that stock").
Use null for entity fields not present. Do not invent values.

Agents:
{agent_taxonomy}

safety_verdict: "safe" for normal queries; otherwise a brief category label
(insider_trading, market_manipulation, money_laundering, guaranteed_returns,
reckless_advice, sanctions_evasion, fraud). Informational only — does NOT block.
""".strip().format(agent_taxonomy=render_agent_taxonomy())


class ClassificationError(RuntimeError):
    """Structured parse failed or response was unusable."""


class ClassificationRefusal(ClassificationError):
    """Model returned a refusal instead of a classification."""


class ClassificationEntities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tickers: list[str] | None = Field(
        ...,
        description=(
            "Stock, fund, commodity, or instrument tickers mentioned in the query. "
            "Use uppercase symbols and include exchange suffixes when relevant, e.g. "
            "AAPL, ASML.AS, HSBA.L, 7203.T. Use null when no ticker is present."
        ),
    )
    amount: float | None = Field(
        ...,
        description=(
            "A monetary or numeric amount mentioned in the query, in the unit of currency. "
            "Use null when absent."
        ),
    )
    currency: str | None = Field(
        ...,
        description=(
            "An ISO 4217 currency code such as USD, EUR, GBP, or JPY. "
            "Use null when absent."
        ),
    )
    rate: float | None = Field(
        ...,
        description=(
            "A decimal interest, return, tax, or discount rate, e.g. 0.08 for 8%. "
            "Use null when absent."
        ),
    )
    period_years: int | None = Field(
        ...,
        description=(
            "An investment, loan, forecast, or planning duration in whole years. "
            "Use null when absent."
        ),
    )
    frequency: Literal["daily", "weekly", "monthly", "yearly"] | None = Field(
        ...,
        description=(
            "Recurring cadence extracted from the query: daily, weekly, monthly, or yearly. "
            "Use null when absent."
        ),
    )
    horizon: str | None = Field(
        ...,
        description=(
            "A forecast or projection horizon token such as 6_months, 1_year, or 5_years. "
            "Use null when absent."
        ),
    )
    time_period: str | None = Field(
        ...,
        description=(
            "A market lookup time period token such as today, this_week, this_month, or this_year. "
            "Use null when absent."
        ),
    )
    topics: list[str] | None = Field(
        ...,
        description=(
            "Financial concepts, support issues, product themes, or other non-ticker topics "
            "mentioned in the query."
        ),
    )
    sectors: list[str] | None = Field(
        ...,
        description=(
            "Market sectors or industries mentioned in the query, e.g. technology or healthcare. "
            "Use null when absent."
        ),
    )
    index: str | None = Field(
        ...,
        description=(
            "A canonical market index name, e.g. S&P 500, FTSE 100, NIKKEI 225, or MSCI World. "
            "Use null when absent."
        ),
    )
    action: Literal["buy", "sell", "hold", "hedge", "rebalance"] | None = Field(
        ...,
        description=(
            "Investment action requested or implied by the query: buy, sell, hold, hedge, "
            "or rebalance. Use null when absent."
        ),
    )
    goal: Literal["retirement", "education", "house", "FIRE", "emergency_fund"] | None = Field(
        ...,
        description=(
            "Financial planning goal: retirement, education, house, FIRE, or emergency_fund. "
            "Use null when absent."
        ),
    )


class ClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str = Field(
        ...,
        description="Concise 2-5 word label of the user's intent (e.g. 'portfolio health check').",
    )
    agent: AgentName = Field(
        ...,
        description="The single best routing target for the query.",
    )
    entities: ClassificationEntities = Field(
        ...,
        description="Extracted entities. Use null for fields that are not present.",
    )
    safety_verdict: str = Field(
        default="safe",
        description="Informational safety assessment: 'safe' or a brief category label if borderline. Does NOT block.",
    )

    _token_usage: tuple[int, int] | None = PrivateAttr(default=None)

    def entities_dict(self) -> dict[str, object]:
        """Entities with nulls stripped (handy for logs and tests)."""
        return self.entities.model_dump(exclude_none=True)


_FALLBACK_ENTITIES = ClassificationEntities(
    tickers=None, amount=None, currency=None, rate=None,
    period_years=None, frequency=None, horizon=None,
    time_period=None, topics=None, sectors=None,
    index=None, action=None, goal=None,
)


_HISTORY_LOOKBACK_TURNS = 3


def _cache_key(query: str, session_history: list[dict[str, str]] | None) -> tuple:
    """Stable, hashable key over query + recent context."""
    norm = query.strip().lower()
    if not session_history:
        return (norm, ())
    recent_user_queries = tuple(
        msg["content"]
        for msg in session_history
        if msg.get("role") == "user"
    )[-_HISTORY_LOOKBACK_TURNS:]
    return (norm, recent_user_queries)


def classify(
    query: str,
    *,
    client: OpenAI,
    session_history: list[dict[str, str]] | None = None,
) -> ClassificationResult:
    """Classify a user query with OpenAI structured outputs.

    Identical (query, recent-context) pairs hit a process-wide TTL cache and
    skip the LLM call entirely. On LLM failure, falls back to general_query
    rather than crashing the request.
    """
    settings = get_settings()

    key = _cache_key(query, session_history)
    cached = _classifier_cache.get(key)
    if cached is not None:
        # Cache hit: zero out token usage so cost metrics don't double-count
        # the original LLM call. Pydantic copy preserves all public fields.
        clone = cached.model_copy()
        clone._token_usage = None
        return clone

    messages: list[dict[str, str]] = [
        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
    ]

    if session_history:
        prior_queries = [
            msg["content"] for msg in session_history if msg.get("role") == "user"
        ][-_HISTORY_LOOKBACK_TURNS:]
        if prior_queries:
            context_block = "Prior user queries in this session:\n" + "\n".join(
                f"- {q}" for q in prior_queries
            )
            messages.append({"role": "user", "content": context_block})

    messages.append({"role": "user", "content": query})

    try:
        response = client.responses.parse(
            model=settings.openai_model,
            input=messages,
            store=False,
            temperature=settings.classifier_temperature,
            text_format=ClassificationResult,
        )
        result = _parse_openai_response(response)
    except (ClassificationRefusal, ClassificationError):
        raise
    except Exception:
        logger.exception("LLM call failed during classification — using fallback")
        return ClassificationResult(
            intent="fallback",
            agent="general_query",
            entities=_FALLBACK_ENTITIES,
            safety_verdict="safe",
        )

    usage = getattr(response, "usage", None)
    inp = getattr(usage, "input_tokens", 0) if usage else 0
    out = getattr(usage, "output_tokens", 0) if usage else 0
    if isinstance(inp, int) and inp > 0:
        result._token_usage = (inp, out)

    _classifier_cache.set(key, result)
    return result


def _parse_openai_response(response: object) -> ClassificationResult:
    parsed = getattr(response, "output_parsed", None)
    if parsed is not None:
        return ClassificationResult.model_validate(parsed)

    for output in getattr(response, "output", []):
        if getattr(output, "type", None) != "message":
            continue

        for item in getattr(output, "content", []):
            if getattr(item, "type", None) == "refusal":
                raise ClassificationRefusal(
                    getattr(item, "refusal", "OpenAI refused to classify the query.")
                )

            parsed = getattr(item, "parsed", None)
            if parsed is not None:
                return ClassificationResult.model_validate(parsed)

    raise ClassificationError("OpenAI response did not include a parsed classification.")

