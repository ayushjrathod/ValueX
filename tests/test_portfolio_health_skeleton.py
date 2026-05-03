"""
Skeleton test for the Portfolio Health agent.

Wire your agent import and remove the skip decorators.
"""
from unittest.mock import MagicMock

import pytest

from src.agents.portfolio_health import (
    ConcentrationRisk,
    Observation,
    PerformanceMetrics,
    PortfolioHealthResult,
    run,
)


def _mock_portfolio_response(concentration_flag: str = "low") -> MagicMock:
    """Build a mock OpenAI response returning a valid PortfolioHealthResult."""
    result = PortfolioHealthResult(
        concentration_risk=ConcentrationRisk(
            top_position_pct=60.4 if concentration_flag == "high" else 15.0,
            top_3_positions_pct=78.2 if concentration_flag == "high" else 40.0,
            flag=concentration_flag,
        ),
        performance=PerformanceMetrics(
            total_return_pct=18.4,
            annualized_return_pct=12.1,
        ),
        benchmark_comparison=None,
        observations=[
            Observation(severity="warning", text="Portfolio is concentrated in a single position."),
            Observation(severity="info", text="Overall returns are solid."),
        ],
    )
    response = MagicMock()
    response.output_parsed = result
    return response


def _mock_empty_portfolio_response() -> MagicMock:
    """Mock response for a user with no positions."""
    result = PortfolioHealthResult(
        concentration_risk=None,
        performance=None,
        benchmark_comparison=None,
        observations=[
            Observation(severity="info", text="Consider starting with a diversified, low-cost index fund."),
        ],
    )
    response = MagicMock()
    response.output_parsed = result
    return response


def test_portfolio_health_does_not_crash_on_empty_portfolio(load_user, mock_llm):
    """
    user_004 has no positions. Agent must not crash.
    """
    mock_llm.responses.parse.return_value = _mock_empty_portfolio_response()

    user = load_user("usr_004")
    response = run(user, llm=mock_llm)  # noqa: F821

    assert response is not None
    assert "disclaimer" in response


def test_portfolio_health_flags_concentration(load_user, mock_llm):
    """
    user_003 has ~60% in NVDA. Agent must surface this.
    """
    mock_llm.responses.parse.return_value = _mock_portfolio_response(concentration_flag="high")

    user = load_user("usr_003")
    response = run(user, llm=mock_llm)  # noqa: F821

    assert response["concentration_risk"]["flag"] in {"high", "warning"}


def test_portfolio_health_includes_disclaimer(load_user, mock_llm):
    mock_llm.responses.parse.return_value = _mock_portfolio_response()

    user = load_user("usr_001")
    response = run(user, llm=mock_llm)  # noqa: F821
    assert response["disclaimer"]
    assert "not investment advice" in response["disclaimer"].lower()
