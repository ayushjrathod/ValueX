import logging
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


AgentName = Literal[
    "portfolio_health",
    "market_research",
    "investment_strategy",
    "financial_planning",
    "financial_calculator",
    "risk_assessment",
    "product_recommendation",
    "predictive_analysis",
    "customer_support",
    "general_query",
]
CLASSIFIER_SYSTEM_PROMPT = """
You are Valura's financial intent classifier.

Return the single best agent, a short intent label, extract only entities
explicitly present or strongly implied by the user query, and provide an
informational safety verdict. For multi-intent queries, choose the primary
intent. For greetings, definitions, educational questions, conversational
messages, and gibberish, use general_query.

If prior conversation context is provided, use it to resolve follow-up references
(e.g. pronouns, "my portfolio", "that stock") to the correct agent and entities.

Agent taxonomy:
- portfolio_health: portfolio assessment, concentration, performance, benchmarking.
- market_research: factual/recent info about instruments, sectors, indices, or market events.
- investment_strategy: buy/sell/hold/hedge/rebalance, allocation, or advice.
- financial_planning: retirement, savings, FIRE, education, house, emergency fund goals.
- financial_calculator: deterministic calculations, DCA, mortgage, tax, future value, FX.
- risk_assessment: risk metrics, exposure, stress tests, what-if scenarios.
- product_recommendation: specific ETFs, funds, or products matching a profile/theme.
- predictive_analysis: forecasts, projections, future value, trend extrapolation.
- customer_support: account, login, transactions, linked bank, app usage issues.
- general_query: education, definitions, greetings, conversation, unrelated/gibberish.

Use null for entity fields that are not present. Do not invent missing values.

For `intent`, write a concise 2-5 word label describing the user's intent
(e.g. "portfolio health check", "stock price lookup", "retirement planning").

For `safety_verdict`, assess whether the query touches harmful financial topics
(insider trading, market manipulation, money laundering, guaranteed returns,
reckless advice, sanctions evasion, fraud). Return "safe" for normal queries,
or a brief category label if the query is borderline.
This verdict is informational only — it does NOT block the request.
""".strip()


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


def classify(
    query: str,
    *,
    client: OpenAI,
    session_history: list[dict[str, str]] | None = None,
) -> ClassificationResult:
    """Classify a user query with OpenAI structured outputs.

    On LLM failure, returns a fallback classification routed to general_query
    rather than crashing the request.
    """
    settings = get_settings()

    messages: list[dict[str, str]] = [
        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
    ]

    if session_history:
        prior_queries = [
            msg["content"] for msg in session_history if msg.get("role") == "user"
        ]
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

