"""
Router: dispatches classified queries to the appropriate agent or returns
a structured response for unimplemented agents.
"""
from typing import Any

from src.classifier.classifier import ClassificationResult


def route(
    classification: ClassificationResult,
    *,
    user: dict[str, Any] | None = None,
    client: object | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Route to the correct agent based on classification result.

    Returns a dict suitable for streaming as an SSE message payload.
    """
    agent = classification.agent
    entities = classification.entities_dict()

    if agent == "portfolio_health":
        return _run_portfolio_health(user=user, client=client, model=model)

    return _format_response(agent, entities)


def _run_portfolio_health(
    *,
    user: dict[str, Any] | None = None,
    client: object | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    from src.agents.portfolio_health import run

    return run(user=user, client=client, model=model)


def _format_response(agent: str, entities: dict[str, Any]) -> dict[str, Any]:
    """Structured response for agents that are not yet implemented."""
    return {
        "status": "not_implemented",
        "agent": agent,
        "entities": entities,
        "message": f"The {agent} agent is not implemented.",
    }
