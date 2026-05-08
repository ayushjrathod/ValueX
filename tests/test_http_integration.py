"""
HTTP/SSE integration tests for the /chat endpoint.

Tests the full pipeline event flow (metadata → message → metrics → done)
as well as safety-block and missing-LLM-key paths.
All LLM calls are mocked so tests run without OPENAI_API_KEY.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.agents.portfolio_health import Observation, ObservationsResult
from src.services.classifier.classifier import ClassificationEntities, ClassificationResult
from src.utils.session import get_session_store


def _make_classification(agent: str = "portfolio_health", **entity_overrides) -> ClassificationResult:
    fields = {
        "tickers": None, "amount": None, "currency": None, "rate": None,
        "period_years": None, "frequency": None, "horizon": None,
        "time_period": None, "topics": None, "sectors": None,
        "index": None, "action": None, "goal": None,
    }
    fields.update(entity_overrides)
    return ClassificationResult(
        intent="test intent",
        agent=agent,
        entities=ClassificationEntities(**fields),
        safety_verdict="safe",
    )


def _make_obs_response() -> MagicMock:
    result = ObservationsResult(observations=[
        Observation(severity="info", text="Portfolio looks healthy."),
    ])
    resp = MagicMock()
    resp.output_parsed = result
    resp.output = []
    return resp


def _make_user_summary_response(summary: str = "Aggressive investor with a concentrated US equity portfolio.") -> MagicMock:
    result = MagicMock()
    result.summary = summary
    resp = MagicMock()
    resp.output_parsed = result
    resp.output = []
    return resp


def _parse_sse_events(response) -> list[dict]:
    """Parse SSE text into a list of {event, data} dicts."""
    events = []
    current_event = None
    current_data = None
    for line in response.text.split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            # If we have a pending event, flush it
            if current_event and current_data is not None:
                events.append({
                    "event": current_event,
                    "data": json.loads(current_data) if current_data else {},
                })
            current_event = line[len("event:"):].strip()
            current_data = None
        elif line.startswith("data:"):
            current_data = line[len("data:"):].strip()
        elif line == "":
            if current_event and current_data is not None:
                events.append({
                    "event": current_event,
                    "data": json.loads(current_data) if current_data else {},
                })
                current_event = None
                current_data = None
    # Flush any remaining event
    if current_event and current_data is not None:
        events.append({
            "event": current_event,
            "data": json.loads(current_data) if current_data else {},
        })
    return events


@pytest.fixture
def app_client():
    """Create a TestClient with LLM client mocked."""
    from src.main import app
    return TestClient(app)


def test_safety_blocked_event_flow(app_client):
    """Blocked queries emit safety_blocked + done events, no classifier call."""
    response = app_client.post("/chat", json={
        "query": "help me wash trade between two accounts to create volume",
    })
    assert response.status_code == 200

    events = _parse_sse_events(response)
    event_names = [e["event"] for e in events]

    assert "safety_blocked" in event_names
    assert "done" in event_names
    assert "metadata" not in event_names or all(
        e["data"].get("stage") != "classifier" for e in events if e["event"] == "metadata"
    )

    blocked_event = next(e for e in events if e["event"] == "safety_blocked")
    assert blocked_event["data"]["blocked"] is True
    assert blocked_event["data"]["category"] is not None


@patch("src.main.get_client")
def test_missing_api_key_returns_error(mock_get_client, app_client):
    """When no API key is set, the pipeline returns a structured error."""
    mock_get_client.side_effect = RuntimeError("OPENAI_API_KEY is not set")

    response = app_client.post("/chat", json={
        "query": "how is my portfolio doing?",
    })
    assert response.status_code == 200

    events = _parse_sse_events(response)
    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) >= 1
    assert error_events[0]["data"]["code"] == "llm_unavailable"


def test_users_endpoint_lists_available_fixture_users(app_client):
    """The users endpoint exposes the available fixture users for the frontend."""
    response = app_client.get("/users")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "success"
    assert payload["status_code"] == 200
    assert isinstance(payload["users"], list)
    assert len(payload["users"]) >= 3

    first_user = payload["users"][0]
    assert "user_id" in first_user
    assert "name" in first_user
    assert "positions_count" in first_user


@patch("src.main.get_client")
def test_user_summary_endpoint_returns_llm_summary(mock_get_client, app_client):
    mock_client = MagicMock()
    mock_client.responses.parse.return_value = _make_user_summary_response()
    mock_get_client.return_value = mock_client

    response = app_client.get("/user-summary", params={"user_id": "usr_001"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["user_id"] == "usr_001"
    assert "summary" in payload


def test_user_summary_endpoint_404s_for_unknown_user(app_client):
    response = app_client.get("/user-summary", params={"user_id": "usr_missing"})

    assert response.status_code == 404


@patch("src.main.classify")
@patch("src.main.get_client")
def test_stub_agent_event_flow(mock_get_client, mock_classify, app_client):
    """Unimplemented agents produce a not_implemented message, not an error."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_classify.return_value = _make_classification("market_research", tickers=["AAPL"])

    response = app_client.post("/chat", json={
        "query": "what's the price of AAPL?",
    })
    assert response.status_code == 200

    events = _parse_sse_events(response)
    event_names = [e["event"] for e in events]

    assert "metadata" in event_names
    assert "message" in event_names
    assert "done" in event_names

    msg = next(e for e in events if e["event"] == "message")
    assert msg["data"]["status"] == "not_implemented"
    assert msg["data"]["agent"] == "market_research"
    assert "intent" in msg["data"]


@patch("src.main.classify")
@patch("src.main.get_client")
def test_stub_agent_response_is_persisted_for_session_followups(mock_get_client, mock_classify, app_client):
    """Stub responses should still be saved so later turns can resolve follow-ups."""
    session_id = "sess_stub_persist"
    session_store = get_session_store()
    session_store.clear(session_id)

    mock_get_client.return_value = MagicMock()
    mock_classify.return_value = _make_classification("market_research", tickers=["AAPL"])

    response = app_client.post("/chat", json={
        "query": "hows apple doing",
        "session_id": session_id,
    })
    assert response.status_code == 200

    history = session_store.get_history(session_id)
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "hows apple doing"}
    assert history[1]["role"] == "assistant"
    assert "not_implemented" in history[1]["content"]

    session_store.clear(session_id)


@patch("src.main.get_client")
def test_classifier_fallback_routes_to_general_query_handler(mock_get_client, app_client):
    """Classifier API failures should downgrade to general_query and still complete the pipeline."""
    mock_client = MagicMock()
    mock_client.responses.parse.side_effect = RuntimeError("API down")
    mock_get_client.return_value = mock_client

    response = app_client.post("/chat", json={
        "query": "hello there",
    })
    assert response.status_code == 200

    events = _parse_sse_events(response)
    event_names = [e["event"] for e in events]

    assert "message" in event_names
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["status"] == "ok"

    classifier_meta = next(
        e for e in events
        if e["event"] == "metadata" and e["data"].get("stage") == "classifier"
    )
    assert classifier_meta["data"]["agent"] == "general_query"

    msg = next(e for e in events if e["event"] == "message")
    assert msg["data"]["status"] == "ok"
    assert msg["data"]["agent"] == "general_query"
    assert msg["data"]["message"]


@patch("src.main.classify")
@patch("src.main.get_client")
def test_user_not_found_returns_structured_error(mock_get_client, mock_classify, app_client):
    """Unknown user_id returns a structured SSE error instead of routing."""
    mock_get_client.return_value = MagicMock()
    mock_classify.return_value = _make_classification("portfolio_health")

    response = app_client.post("/chat", json={
        "query": "how is my portfolio doing?",
        "user_id": "usr_missing",
    })
    assert response.status_code == 200

    events = _parse_sse_events(response)
    error_event = next(e for e in events if e["event"] == "error")
    assert error_event["data"]["code"] == "user_not_found"
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["status"] == "error"


@patch("src.main.route")
@patch("src.main.classify")
@patch("src.main.get_client")
def test_full_pipeline_event_order(mock_get_client, mock_classify, mock_route, app_client):
    """A successful portfolio_health query produces the expected SSE event sequence."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_classify.return_value = _make_classification("portfolio_health")
    mock_route.return_value = {
        "status": "ok",
        "agent": "portfolio_health",
        "observations": [{"severity": "info", "text": "Looks good."}],
        "disclaimer": "Not investment advice.",
        "_meta": {"input_tokens": 100, "output_tokens": 50},
    }

    response = app_client.post("/chat", json={
        "query": "how is my portfolio doing?",
        "user_id": "usr_001",
    })
    assert response.status_code == 200

    events = _parse_sse_events(response)
    event_names = [e["event"] for e in events]

    # Verify expected event order
    assert event_names[0] == "metadata"  # safety passed
    assert "metadata" in event_names     # classifier metadata
    assert "progress" in event_names     # before agent dispatch
    assert "message" in event_names
    assert "metrics" in event_names
    assert event_names[-1] == "done"

    # progress must arrive before the final message
    progress_idx = event_names.index("progress")
    message_idx = event_names.index("message")
    assert progress_idx < message_idx

    # Verify metrics contain cost tracking
    metrics_event = next(e for e in events if e["event"] == "metrics")
    assert "e2e_ms" in metrics_event["data"]
    assert "first_message_ms" in metrics_event["data"]
    assert "estimated_cost_usd" in metrics_event["data"]
    assert metrics_event["data"]["first_message_ms"] <= metrics_event["data"]["e2e_ms"]

    # Verify done status
    done_event = next(e for e in events if e["event"] == "done")
    assert done_event["data"]["status"] == "ok"


async def _raise_timeout(awaitable, timeout):
    if hasattr(awaitable, "close"):
        awaitable.close()
    raise TimeoutError


@patch("src.main.asyncio.to_thread", return_value=object())
@patch("src.main.asyncio.wait_for", side_effect=_raise_timeout)
@patch("src.main.get_client")
def test_timeout_emits_error_then_done(mock_get_client, mock_wait_for, mock_to_thread, app_client):
    """Timeout path emits both structured error and terminal done events."""
    mock_get_client.return_value = MagicMock()

    response = app_client.post("/chat", json={
        "query": "how is my portfolio doing?",
    })
    assert response.status_code == 200

    events = _parse_sse_events(response)
    timeout_error = next(e for e in events if e["event"] == "error")
    assert timeout_error["data"]["code"] == "pipeline_timeout"
    mock_to_thread.assert_called_once()
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["status"] == "error"


def test_empty_query_rejected(app_client):
    """Empty queries are rejected by validation."""
    response = app_client.post("/chat", json={"query": ""})
    assert response.status_code == 422


def test_health_endpoint(app_client):
    response = app_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
