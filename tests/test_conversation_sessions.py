"""
Tests for conversation session handling: follow-up resolution, topic switching,
and ambiguous queries.

Uses the gold conversation fixtures from fixtures/conversations/.

Two modes:
  1. Live LLM (requires OPENAI_API_KEY): sends real queries with session
     context through the classifier and checks routing against the gold file.
  2. Mock (always runs): verifies that session history is correctly formatted
     and passed to the LLM — does NOT claim routing accuracy.
"""
import os
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.classifier import classify
from src.classifier.classifier import ClassificationEntities, ClassificationResult

# Fixture agent names may use "portfolio_query" which maps to "portfolio_health"
# in our taxonomy. This mapping normalises the expected values.
_AGENT_ALIAS = {
    "portfolio_query": "portfolio_health",
}


def _normalise_agent(agent: str) -> str:
    return _AGENT_ALIAS.get(agent, agent)


def _history_from_prior_turns(turns: list[str]) -> list[dict[str, str]]:
    """Build a session history list from prior user turns."""
    history: list[dict[str, str]] = []
    for turn in turns:
        history.append({"role": "user", "content": turn})
        history.append({"role": "assistant", "content": "{}"})
    return history


def _has_openai_key() -> bool:
    from src.config.settings import get_settings
    try:
        s = get_settings()
        return bool(s.openai_api_key)
    except Exception:
        return bool(os.environ.get("OPENAI_API_KEY"))


_skip_no_key = pytest.mark.skipif(
    not _has_openai_key(),
    reason="OPENAI_API_KEY not set — skipping live classifier test",
)


def _build_mock_response(agent: str, entities: dict[str, Any] | None = None) -> MagicMock:
    entity_fields = {
        "tickers": None, "amount": None, "currency": None, "rate": None,
        "period_years": None, "frequency": None, "horizon": None,
        "time_period": None, "topics": None, "sectors": None,
        "index": None, "action": None, "goal": None,
    }
    if entities:
        valid_keys = set(entity_fields.keys())
        entity_fields.update({k: v for k, v in entities.items() if k in valid_keys})
    result = ClassificationResult(
        intent="test",
        agent=_normalise_agent(agent),
        entities=ClassificationEntities(**entity_fields),
        safety_verdict="safe",
    )
    resp = MagicMock()
    resp.output_parsed = result
    return resp


# ---------------------------------------------------------------------------
# Live-LLM conversation tests (the real tests)
# ---------------------------------------------------------------------------

@_skip_no_key
def test_follow_up_session_live(conversation_test_cases):
    """Follow-up resolution: ≥ 75% routing accuracy with real LLM."""
    from src.utils.llm import get_client
    client = get_client()
    cases = conversation_test_cases("follow_up_session")

    correct = 0
    for case in cases:
        history = _history_from_prior_turns(case["prior_user_turns"])
        result = classify(
            case["current_user_turn"],
            client=client,
            session_history=history or None,
        )
        expected_agent = _normalise_agent(case["expected"]["agent"])
        if result.agent == expected_agent:
            correct += 1

    accuracy = correct / len(cases)
    assert accuracy >= 0.75, (
        f"Follow-up routing accuracy {accuracy:.2%} below 75% ({correct}/{len(cases)})"
    )


@_skip_no_key
def test_multi_intent_session_live(conversation_test_cases):
    """Topic-switch handling: ≥ 75% routing accuracy with real LLM."""
    from src.utils.llm import get_client
    client = get_client()
    cases = conversation_test_cases("multi_intent_session")

    correct = 0
    for case in cases:
        history = _history_from_prior_turns(case["prior_user_turns"])
        result = classify(
            case["current_user_turn"],
            client=client,
            session_history=history or None,
        )
        expected_agent = _normalise_agent(case["expected"]["agent"])
        if result.agent == expected_agent:
            correct += 1

    accuracy = correct / len(cases)
    assert accuracy >= 0.75, (
        f"Multi-intent routing accuracy {accuracy:.2%} below 75% ({correct}/{len(cases)})"
    )


@_skip_no_key
def test_ambiguous_session_live(conversation_test_cases):
    """Ambiguous/typo handling: ≥ 60% routing accuracy with real LLM."""
    from src.utils.llm import get_client
    client = get_client()
    cases = conversation_test_cases("ambiguous_session")

    correct = 0
    for case in cases:
        history = _history_from_prior_turns(case["prior_user_turns"])
        result = classify(
            case["current_user_turn"],
            client=client,
            session_history=history or None,
        )
        expected_agent = _normalise_agent(case["expected"]["agent"])
        if result.agent == expected_agent:
            correct += 1

    accuracy = correct / len(cases)
    assert accuracy >= 0.60, (
        f"Ambiguous routing accuracy {accuracy:.2%} below 60% ({correct}/{len(cases)})"
    )


# ---------------------------------------------------------------------------
# Mock-based: verifies session-history plumbing (always runs, no accuracy claim)
# ---------------------------------------------------------------------------

def test_session_history_included_in_llm_call(mock_llm):
    """Verify classify() includes prior user queries as a context block when history is provided."""
    mock_llm.responses.parse.return_value = _build_mock_response("general_query")

    history = [
        {"role": "user", "content": "What's happening with Nvidia?"},
        {"role": "assistant", "content": "{}"},
    ]
    classify("How much do I own?", client=mock_llm, session_history=history)

    call_kwargs = mock_llm.responses.parse.call_args
    messages = call_kwargs.kwargs.get("input") or call_kwargs[1].get("input")
    user_messages = [m for m in messages if m["role"] == "user"]

    # Should have: context block (prior queries) + current query
    assert len(user_messages) == 2, "Expected context block + current query"
    assert "Nvidia" in user_messages[0]["content"], (
        "Context block should contain prior user query"
    )
    assert "How much do I own?" in user_messages[1]["content"]


def test_no_history_omits_context_block(mock_llm):
    """Verify classify() does NOT inject a context block when history is None."""
    mock_llm.responses.parse.return_value = _build_mock_response("general_query")

    classify("How is my portfolio?", client=mock_llm, session_history=None)

    call_kwargs = mock_llm.responses.parse.call_args
    messages = call_kwargs.kwargs.get("input") or call_kwargs[1].get("input")
    user_messages = [m for m in messages if m["role"] == "user"]
    assert len(user_messages) == 1, "No context block expected without history"
    assert "How is my portfolio?" in user_messages[0]["content"]


def test_empty_history_omits_context_block(mock_llm):
    """Verify classify() handles empty history list gracefully."""
    mock_llm.responses.parse.return_value = _build_mock_response("general_query")

    classify("Hello", client=mock_llm, session_history=[])

    call_kwargs = mock_llm.responses.parse.call_args
    messages = call_kwargs.kwargs.get("input") or call_kwargs[1].get("input")
    user_messages = [m for m in messages if m["role"] == "user"]
    assert len(user_messages) == 1, "No context block expected with empty history"


def test_multi_turn_history_format(mock_llm):
    """Verify multiple prior turns are all included in the context block."""
    mock_llm.responses.parse.return_value = _build_mock_response("general_query")

    history = [
        {"role": "user", "content": "What's AAPL doing?"},
        {"role": "assistant", "content": "{}"},
        {"role": "user", "content": "And MSFT?"},
        {"role": "assistant", "content": "{}"},
    ]
    classify("compare them", client=mock_llm, session_history=history)

    call_kwargs = mock_llm.responses.parse.call_args
    messages = call_kwargs.kwargs.get("input") or call_kwargs[1].get("input")
    user_messages = [m for m in messages if m["role"] == "user"]

    context_block = user_messages[0]["content"]
    assert "AAPL" in context_block, "Context block should include first prior query"
    assert "MSFT" in context_block, "Context block should include second prior query"
    assert "compare them" in user_messages[1]["content"]
