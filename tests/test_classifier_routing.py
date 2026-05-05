"""
Classifier routing accuracy tests against the gold-standard labeled queries.

Two modes:
  1. Live LLM (requires OPENAI_API_KEY): sends real queries through the
     classifier prompt and checks routing accuracy ≥ 85% against the gold file.
  2. Mock (always runs): verifies the classifier's response-parsing and
     fallback logic — but does NOT claim routing accuracy.
"""
import os
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.agents.catalog import AGENT_DESCRIPTIONS
from src.classifier import classify
from src.classifier.classifier import ClassificationEntities, ClassificationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_ticker(t: str) -> str:
    """Case-fold and drop the exchange suffix (AAPL.US → AAPL)."""
    return t.upper().split(".")[0]


def matches_entities(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    """
    Subset match with normalization.  `actual` must contain every value in
    `expected`; extra fields and extra values are allowed.
    """
    for field, exp_value in expected.items():
        act_value = actual.get(field)
        if act_value is None:
            return False

        if field == "tickers":
            exp_set = {_normalize_ticker(t) for t in exp_value}
            act_set = {_normalize_ticker(t) for t in act_value}
            if not exp_set.issubset(act_set):
                return False
        elif field in ("topics", "sectors"):
            exp_set = {s.lower() for s in exp_value}
            act_set = {s.lower() for s in act_value}
            if not exp_set.issubset(act_set):
                return False
        elif field in ("amount", "rate"):
            if abs(act_value - exp_value) > abs(exp_value) * 0.05:
                return False
        elif field == "period_years":
            if int(act_value) != int(exp_value):
                return False
        else:
            if str(act_value).lower() != str(exp_value).lower():
                return False
    return True


def _has_openai_key() -> bool:
    """Check whether a usable API key is configured (env var or .env)."""
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


# ---------------------------------------------------------------------------
# Live-LLM routing accuracy (the real test)
# ---------------------------------------------------------------------------

@_skip_no_key
def test_classifier_routing_accuracy(gold_classifier_queries):
    """
    Threshold: ≥ 85% routing accuracy against the gold file using the real LLM.
    """
    from src.utils.llm import get_client
    client = get_client()

    correct = 0
    misrouted: list[dict] = []

    for case in gold_classifier_queries:
        result = classify(case["query"], client=client)
        if result.agent == case["expected_agent"]:
            correct += 1
        else:
            misrouted.append({
                "query": case["query"],
                "expected": case["expected_agent"],
                "got": result.agent,
            })

    accuracy = correct / len(gold_classifier_queries)
    detail = "\n".join(
        f"  {m['query']!r}: expected {m['expected']}, got {m['got']}"
        for m in misrouted
    )
    assert accuracy >= 0.85, (
        f"Routing accuracy {accuracy:.2%} ({correct}/{len(gold_classifier_queries)}) "
        f"below 85%.\nMisrouted:\n{detail}"
    )
    print(f"\nRouting accuracy: {accuracy:.2%} ({correct}/{len(gold_classifier_queries)})")


# ---------------------------------------------------------------------------
# Live-LLM entity extraction
# ---------------------------------------------------------------------------

@_skip_no_key
def test_classifier_entity_extraction(gold_classifier_queries):
    """
    Entity match rate against the gold file using the real LLM.
    Soft threshold: ≥ 60% subset match.
    """
    from src.utils.llm import get_client
    client = get_client()

    matched = 0
    total_with_entities = 0

    for case in gold_classifier_queries:
        if not case["expected_entities"]:
            continue
        total_with_entities += 1
        result = classify(case["query"], client=client)
        if matches_entities(result.entities_dict(), case["expected_entities"]):
            matched += 1

    rate = matched / total_with_entities if total_with_entities else 0.0
    print(f"\nEntity match rate: {rate:.2%} ({matched}/{total_with_entities})")
    assert rate >= 0.60, f"Entity match rate {rate:.2%} below 60%"


# ---------------------------------------------------------------------------
# Mock-based: verifies parsing & fallback logic (always runs, no accuracy claim)
# ---------------------------------------------------------------------------

def _build_mock_response(agent: str, entities: dict[str, Any]) -> MagicMock:
    """Build a mock OpenAI response with output_parsed set to a ClassificationResult."""
    entity_fields = {
        "tickers": None, "amount": None, "currency": None, "rate": None,
        "period_years": None, "frequency": None, "horizon": None,
        "time_period": None, "topics": None, "sectors": None,
        "index": None, "action": None, "goal": None,
    }
    entity_fields.update(entities)
    result = ClassificationResult(
        intent="test intent",
        agent=agent,
        entities=ClassificationEntities(**entity_fields),
        safety_verdict="safe",
    )
    response = MagicMock()
    response.output_parsed = result
    return response


def test_classifier_parses_structured_response(mock_llm):
    """Verify classify() correctly parses a well-formed structured response."""
    mock_resp = _build_mock_response("market_research", {"tickers": ["AAPL"]})
    mock_llm.responses.parse.return_value = mock_resp

    result = classify("what's the price of AAPL?", client=mock_llm)
    assert result.agent == "market_research"
    assert result.entities.tickers == ["AAPL"]


def test_classifier_fallback_on_llm_failure(mock_llm):
    """Verify classify() returns general_query fallback when the LLM call raises."""
    mock_llm.responses.parse.side_effect = RuntimeError("API down")

    result = classify("anything", client=mock_llm)
    assert result.agent == "general_query"
    assert result.intent == "fallback"


def test_classifier_prompt_contains_all_agents(mock_llm):
    """Verify the system prompt includes every agent name from the taxonomy."""
    mock_resp = _build_mock_response("general_query", {})
    mock_llm.responses.parse.return_value = mock_resp

    classify("hello", client=mock_llm)

    call_kwargs = mock_llm.responses.parse.call_args
    messages = call_kwargs.kwargs.get("input") or call_kwargs[1].get("input")
    system_msg = next(m for m in messages if m["role"] == "system")

    for agent in AGENT_DESCRIPTIONS:
        assert agent.value in system_msg["content"], f"Agent {agent.value!r} missing from system prompt"


def test_classifier_uses_structured_output_schema(mock_llm):
    """Verify classify() requests ClassificationResult as the structured output schema."""
    mock_resp = _build_mock_response("general_query", {})
    mock_llm.responses.parse.return_value = mock_resp

    classify("hello", client=mock_llm)

    call_kwargs = mock_llm.responses.parse.call_args
    text_format = call_kwargs.kwargs.get("text_format")
    assert text_format is ClassificationResult, (
        f"Expected text_format=ClassificationResult, got {text_format}"
    )


def test_classifier_query_appears_in_messages(mock_llm):
    """Verify the user's query text is passed to the LLM in the messages."""
    mock_resp = _build_mock_response("general_query", {})
    mock_llm.responses.parse.return_value = mock_resp

    classify("how is my portfolio doing", client=mock_llm)

    call_kwargs = mock_llm.responses.parse.call_args
    messages = call_kwargs.kwargs.get("input") or call_kwargs[1].get("input")
    user_messages = [m["content"] for m in messages if m["role"] == "user"]
    assert any("how is my portfolio doing" in msg for msg in user_messages)
