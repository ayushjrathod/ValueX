from unittest.mock import MagicMock

from src.agents.catalog import AgentName
from src.agents.contracts import AgentResponse
from src.agents.registry import AGENT_REGISTRY
from src.agents.router import route
from src.services.classifier.classifier import ClassificationEntities, ClassificationResult


def _make_classification(agent: AgentName) -> ClassificationResult:
    return ClassificationResult(
        intent="test intent",
        agent=agent,
        entities=ClassificationEntities(
            tickers=["AAPL"],
            amount=None,
            currency=None,
            rate=None,
            period_years=None,
            frequency=None,
            horizon=None,
            time_period=None,
            topics=None,
            sectors=None,
            index=None,
            action=None,
            goal=None,
        ),
        safety_verdict="safe",
    )


def test_route_dispatches_through_registry(monkeypatch):
    captured = {}

    def handler(request):
        captured["request"] = request
        return AgentResponse(status="ok", agent=request.agent, message="handled")

    monkeypatch.setitem(AGENT_REGISTRY, AgentName.PORTFOLIO_HEALTH, handler)

    result = route(
        _make_classification(AgentName.PORTFOLIO_HEALTH),
        user={"id": "usr_001"},
        client=MagicMock(),
        query="how is my portfolio?",
        history=[{"role": "user", "content": "earlier turn"}],
    )

    assert result["status"] == "ok"
    assert result["agent"] == AgentName.PORTFOLIO_HEALTH.value
    assert captured["request"].entities["tickers"] == ["AAPL"]
    assert captured["request"].query == "how is my portfolio?"


def test_route_returns_structured_stub_for_unregistered_agent():
    result = route(
        _make_classification(AgentName.GENERAL_QUERY),
        user=None,
        client=MagicMock(),
    )

    assert result["status"] == "not_implemented"
    assert result["agent"] == AgentName.GENERAL_QUERY.value
    assert result["entities"] == {"tickers": ["AAPL"]}


def test_market_research_is_explicitly_registered():
    handler = AGENT_REGISTRY[AgentName.MARKET_RESEARCH]
    request = MagicMock()
    request.intent = "price lookup"
    request.entities = {"tickers": ["AAPL"]}
    request.agent = AgentName.MARKET_RESEARCH

    response = handler(request)

    assert AgentName.MARKET_RESEARCH in AGENT_REGISTRY
    assert response.status == "not_implemented"
    assert response.agent == AgentName.MARKET_RESEARCH
