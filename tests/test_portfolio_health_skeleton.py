"""
Tests for the Portfolio Health agent.

The agent prefetches market data deterministically (no LLM tool-calling loop)
and then runs a single LLM call for the structured observations. Tests stub
both the yfinance helpers and the observations LLM call so they run without
network access or OPENAI_API_KEY.
"""
from unittest.mock import MagicMock

import pytest

from src.agents.portfolio_health import Observation, ObservationsResult, run


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


@pytest.fixture(autouse=True)
def _stub_market_data(monkeypatch):
    """Block real yfinance calls in unit tests. Tests opt-in to specific data."""
    monkeypatch.setattr(
        "src.agents.portfolio_health.fetch_prices",
        lambda tickers: {},
    )
    monkeypatch.setattr(
        "src.agents.portfolio_health.fetch_benchmark",
        lambda symbol, period: {"error": "stubbed in tests"},
    )


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
    assert any(
        keyword in observation["text"].lower()
        for observation in response["observations"]
        for keyword in ("start", "begin", "first", "consider", "diversif")
    )


def test_portfolio_health_flags_concentration(load_user, mock_llm):
    """usr_003 has ~80% in NVDA. Concentration flag derives from cost basis when no live prices."""
    mock_llm.responses.parse.return_value = _mock_observations_response()

    user = load_user("usr_003")
    response = run(user, client=mock_llm)

    assert response["concentration_risk"]["flag"] in {"high", "warning"}
    assert response["concentration_risk"]["top_position_pct"] > 50


def test_portfolio_health_includes_disclaimer(load_user, mock_llm):
    mock_llm.responses.parse.return_value = _mock_observations_response()

    user = load_user("usr_001")
    response = run(user, client=mock_llm)
    assert response["disclaimer"]
    assert "not investment advice" in response["disclaimer"].lower()


def test_portfolio_health_no_performance_without_live_prices(load_user, mock_llm):
    """When no live prices are fetched, performance is omitted (can't compute without prices)."""
    mock_llm.responses.parse.return_value = _mock_observations_response()

    user = load_user("usr_001")
    response = run(user, client=mock_llm)

    assert "performance" not in response
    assert response["concentration_risk"] is not None


def test_portfolio_health_focus_tickers_accepted(load_user, mock_llm):
    """Agent accepts focus_tickers kwarg without error."""
    mock_llm.responses.parse.return_value = _mock_observations_response()

    user = load_user("usr_001")
    response = run(user, client=mock_llm, focus_tickers=["AAPL"])

    assert response["status"] == "ok"
    assert "observations" in response


def test_portfolio_health_uses_live_prices_when_available(load_user, mock_llm, monkeypatch):
    """When fetch_prices returns data, performance and benchmark_comparison are computed."""
    mock_llm.responses.parse.return_value = _mock_observations_response()

    monkeypatch.setattr(
        "src.agents.portfolio_health.fetch_prices",
        lambda tickers: {
            t: {"ticker": t, "price": 200.0, "currency": "USD"} for t in tickers
        },
    )
    monkeypatch.setattr(
        "src.agents.portfolio_health.fetch_benchmark",
        lambda symbol, period: {
            "symbol": symbol, "period": period, "return_pct": 12.0,
            "start_price": 100.0, "end_price": 112.0, "data_points": 252,
        },
    )

    user = load_user("usr_001")
    response = run(user, client=mock_llm)

    assert "performance" in response
    assert "benchmark_comparison" in response
    assert response["benchmark_comparison"]["benchmark"] == "QQQ"


def test_portfolio_health_benchmark_hint_overrides_user_pref(load_user, mock_llm, monkeypatch):
    """entities.index from the classifier wins over the user's stored preference."""
    mock_llm.responses.parse.return_value = _mock_observations_response()

    seen_symbols: list[str] = []

    def _capture_bench(symbol: str, period: str) -> dict:
        seen_symbols.append(symbol)
        return {"error": "skipped"}

    monkeypatch.setattr("src.agents.portfolio_health.fetch_benchmark", _capture_bench)

    # usr_003 has preferred_benchmark "S&P 500" → SPY by default.
    user = load_user("usr_003")
    run(user, client=mock_llm, benchmark_hint="NASDAQ")

    assert seen_symbols == ["QQQ"]
