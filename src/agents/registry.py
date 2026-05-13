from src.agents.catalog import AgentName
from src.agents.contracts import AgentHandler, AgentRequest, AgentResponse
from src.agents.general_query import run as run_general_query
from src.agents.market_research import run as run_market_research
from src.agents.portfolio_health import run as run_portfolio_health


def _run_portfolio_health(request: AgentRequest) -> AgentResponse:
    response = run_portfolio_health(
        user=request.user,
        client=request.client,
        model=request.model,
        query=request.query,
        history=request.history,
        focus_tickers=request.entities.get("tickers"),
        benchmark_hint=request.entities.get("index"),
    )
    return AgentResponse.model_validate(response)


def _run_market_research(request: AgentRequest) -> AgentResponse:
    return run_market_research(request)


def _run_general_query(request: AgentRequest) -> AgentResponse:
    return run_general_query(request)


AGENT_REGISTRY: dict[AgentName, AgentHandler] = {
    AgentName.PORTFOLIO_HEALTH: _run_portfolio_health,
    AgentName.MARKET_RESEARCH: _run_market_research,
    AgentName.GENERAL_QUERY: _run_general_query,
}


def build_not_implemented_response(request: AgentRequest) -> AgentResponse:
    return AgentResponse(
        status="not_implemented",
        intent=request.intent,
        agent=request.agent,
        entities=request.entities,
        message=f"The {request.agent} agent is not implemented in this build.",
    )
