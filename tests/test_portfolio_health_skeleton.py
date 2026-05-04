"""
Tests for the Portfolio Health agent.

Architecture: tool-calling loop (responses.create) + observation generation
(responses.parse with ObservationsResult).  Mocks replace both LLM calls so
tests run without OPENAI_API_KEY.
"""
from unittest.mock import MagicMock

from src.agents.portfolio_health import Observation, ObservationsResult, run


def _mock_no_tool_calls() -> MagicMock:
    """Simulate a responses.create() round with zero tool calls."""
    resp = MagicMock()
    resp.output = []
    return resp


def _mock_observations_response(observations: list[Observation] | None = None) -> MagicMock:
    """Simulate a responses.parse() call returning ObservationsResult."""
    obs = observations or [
        Observation(severity="info", text="Your portfolio looks healthy overall."),
    ]
    result = ObservationsResult(observations=obs)
    resp = MagicMock()
    resp.output_parsed = result
    resp.output = []
    return resp


def test_portfolio_health_does_not_crash_on_empty_portfolio(load_user, mock_llm):
    """usr_004 has no positions. Agent must not crash."""
    mock_llm.responses.parse.return_value = _mock_observations_response(
        [Observation(severity="info", text="Consider starting with a low-cost index fund.")]
    )

    user = load_user("usr_004")
    response = run(user, client=mock_llm)

    assert response is not None
    assert response["status"] == "ok"
    assert "disclaimer" in response
    assert "concentration_risk" not in response
    assert "performance" not in response


def test_portfolio_health_flags_concentration(load_user, mock_llm):
    """usr_003 has ~80% in NVDA. Deterministic metrics must flag this."""
    mock_llm.responses.create.return_value = _mock_no_tool_calls()
    mock_llm.responses.parse.return_value = _mock_observations_response()

    user = load_user("usr_003")
    response = run(user, client=mock_llm)

    assert response["concentration_risk"]["flag"] in {"high", "warning"}
    assert response["concentration_risk"]["top_position_pct"] > 50


def test_portfolio_health_includes_disclaimer(load_user, mock_llm):
    mock_llm.responses.create.return_value = _mock_no_tool_calls()
    mock_llm.responses.parse.return_value = _mock_observations_response()

    user = load_user("usr_001")
    response = run(user, client=mock_llm)
    assert response["disclaimer"]
    assert "not investment advice" in response["disclaimer"].lower()


def test_portfolio_health_no_performance_without_live_prices(load_user, mock_llm):
    """When no live prices are fetched, performance is omitted (can't compute without prices)."""
    mock_llm.responses.create.return_value = _mock_no_tool_calls()
    mock_llm.responses.parse.return_value = _mock_observations_response()

    user = load_user("usr_001")
    response = run(user, client=mock_llm)

    assert "performance" not in response
    assert response["concentration_risk"] is not None


def test_portfolio_health_focus_tickers_accepted(load_user, mock_llm):
    """Agent accepts focus_tickers kwarg without error."""
    mock_llm.responses.create.return_value = _mock_no_tool_calls()
    mock_llm.responses.parse.return_value = _mock_observations_response()

    user = load_user("usr_001")
    response = run(user, client=mock_llm, focus_tickers=["AAPL"])

    assert response["status"] == "ok"
    assert "observations" in response
