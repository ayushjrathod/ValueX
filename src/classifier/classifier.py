from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.config.settings import get_settings


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

Return the single best agent and extract only entities explicitly present or
strongly implied by the user query. For multi-intent queries, choose the primary
intent. For greetings, definitions, educational questions, conversational
messages, and gibberish, use general_query.

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
""".strip()


class ClassificationError(RuntimeError):
    """Raised when the classifier cannot produce a parsed structured result."""


class ClassificationRefusal(ClassificationError):
    """Raised when OpenAI refuses the classification request."""


class ClassificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        description="The raw user query to route to the most appropriate financial assistant agent.",
    )


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

    agent: AgentName = Field(
        ...,
        description="The single best routing target for the query.",
    )
    entities: ClassificationEntities = Field(
        ...,
        description="Extracted entities. Use null for fields that are not present.",
    )

    def entities_dict(self) -> dict[str, object]:
        """Return only populated entities for fixture-style subset matching."""
        return self.entities.model_dump(exclude_none=True)


def classify(
    query: str,
    *,
    client: object | None = None,
    model: str | None = None,
) -> ClassificationResult:
    """Classify a user query with OpenAI structured outputs."""
    settings = get_settings()
    openai_client = client

    response = openai_client.responses.parse(
        model=model or settings.openai_model,
        input=[
            {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        store=False,
        temperature=0.1,
        text_format=ClassificationResult,
    )
    return _parse_openai_response(response)


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

