from enum import StrEnum


class AgentName(StrEnum):
    PORTFOLIO_HEALTH = "portfolio_health"
    MARKET_RESEARCH = "market_research"
    INVESTMENT_STRATEGY = "investment_strategy"
    FINANCIAL_PLANNING = "financial_planning"
    FINANCIAL_CALCULATOR = "financial_calculator"
    RISK_ASSESSMENT = "risk_assessment"
    PRODUCT_RECOMMENDATION = "product_recommendation"
    PREDICTIVE_ANALYSIS = "predictive_analysis"
    CUSTOMER_SUPPORT = "customer_support"
    GENERAL_QUERY = "general_query"


AGENT_DESCRIPTIONS: dict[AgentName, str] = {
    AgentName.PORTFOLIO_HEALTH: "portfolio assessment, concentration, performance, benchmarking.",
    AgentName.MARKET_RESEARCH: "factual/recent info about instruments, sectors, indices, or market events.",
    AgentName.INVESTMENT_STRATEGY: "buy/sell/hold/hedge/rebalance, allocation, or advice.",
    AgentName.FINANCIAL_PLANNING: "retirement, savings, FIRE, education, house, emergency fund goals.",
    AgentName.FINANCIAL_CALCULATOR: "deterministic calculations, DCA, mortgage, tax, future value, FX.",
    AgentName.RISK_ASSESSMENT: "risk metrics, exposure, stress tests, what-if scenarios.",
    AgentName.PRODUCT_RECOMMENDATION: "specific ETFs, funds, or products matching a profile/theme.",
    AgentName.PREDICTIVE_ANALYSIS: "forecasts, projections, future value, trend extrapolation.",
    AgentName.CUSTOMER_SUPPORT: "account, login, transactions, linked bank, app usage issues.",
    AgentName.GENERAL_QUERY: "education, definitions, greetings, conversation, unrelated/gibberish.",
}


def render_agent_taxonomy() -> str:
    return "\n".join(
        f"- {agent.value}: {description}"
        for agent, description in AGENT_DESCRIPTIONS.items()
    )
