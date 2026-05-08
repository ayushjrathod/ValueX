"""
Router: dispatches classified queries to the appropriate agent or returns
a structured response for unimplemented agents.
"""
from typing import Any

from openai import OpenAI

from src.agents.contracts import AgentRequest
from src.agents.registry import AGENT_REGISTRY, build_not_implemented_response
from src.services.classifier.classifier import ClassificationResult


def route(
    classification: ClassificationResult,
    *,
    user: dict[str, Any] | None = None,
    client: OpenAI,
    model: str | None = None,
    query: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Route to the correct agent based on classification result.

    Returns a dict suitable for streaming as an SSE message payload.
    *query* and *history* are forwarded to the agent for follow-up
    resolution via session memory.
    """
    request = AgentRequest(
        agent=classification.agent,
        intent=classification.intent,
        entities=classification.entities_dict(),
        user=user,
        client=client,
        model=model,
        query=query,
        history=history,
    )
    handler = AGENT_REGISTRY.get(request.agent)
    if handler is None:
        return build_not_implemented_response(request).to_payload()
    return handler(request).to_payload()
