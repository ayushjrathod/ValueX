"""
Pipeline cost and latency tracking.

Provides model pricing data and cost estimation for OpenAI API calls.
Used by the HTTP layer to emit per-request metrics.
"""

import json
import logging
from typing import Any

from src.config.settings import MODEL_PRICING_USD_PER_1M_TOKENS

logger = logging.getLogger(__name__)


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    """Return estimated USD cost, or None if model pricing is unknown."""
    pricing = MODEL_PRICING_USD_PER_1M_TOKENS.get(model)
    if pricing is None:
        return None
    return (
        input_tokens * pricing["input"] / 1_000_000
        + output_tokens * pricing["output"] / 1_000_000
    )

def track_and_log_metrics(
    agent_response: dict[str, Any],
    classification: Any,
    metrics: dict[str, Any],
    t_start: float,
    t_classify: float,
    t_agent: float,
    t_end: float,
    settings: Any,
    user_id: str | None,
) -> None:
    meta = agent_response.pop("_meta", {})
    agent_input_tokens = meta.get("input_tokens", 0)
    agent_output_tokens = meta.get("output_tokens", 0)

    classifier_tokens = getattr(classification, "_token_usage", None)
    if classifier_tokens:
        cls_in, cls_out = classifier_tokens
    else:
        cls_in, cls_out = 0, 0

    total_input = agent_input_tokens + cls_in
    total_output = agent_output_tokens + cls_out

    model_name = settings.openai_model
    cost = estimate_cost(model_name, total_input, total_output)

    e2e_ms = round((t_end - t_start) * 1000)
    metrics["agent_ms"] = round((t_agent - t_classify) * 1000)
    metrics["e2e_ms"] = e2e_ms
    metrics["model"] = model_name
    metrics["classifier_input_tokens"] = cls_in
    metrics["classifier_output_tokens"] = cls_out
    metrics["agent_input_tokens"] = agent_input_tokens
    metrics["agent_output_tokens"] = agent_output_tokens
    metrics["total_input_tokens"] = total_input
    metrics["total_output_tokens"] = total_output
    metrics["estimated_cost_usd"] = round(cost, 6) if cost is not None else None

    if e2e_ms > settings.e2e_warn_threshold_s * 1000:
        logger.warning(
            "Pipeline e2e %dms exceeds %.0fs target",
            e2e_ms, settings.e2e_warn_threshold_s,
        )

    logger.info(
        "request_complete %s",
        json.dumps({
            "user_id": user_id,
            "agent": classification.agent,
            "model": model_name,
            "safety_ms": metrics["safety_ms"],
            "classifier_ms": metrics["classifier_ms"],
            "agent_ms": metrics["agent_ms"],
            "e2e_ms": e2e_ms,
            "tokens": {"input": total_input, "output": total_output},
            "cost_usd": metrics["estimated_cost_usd"],
            "under_budget": cost < settings.cost_budget_usd if cost is not None else None,
        }),
    )
