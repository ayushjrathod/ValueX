"""
Router: dispatches classified queries to the appropriate agent or returns
a structured response for unimplemented agents.
"""
from typing import Any

from openai import OpenAI

from src.classifier.classifier import ClassificationResult


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
    agent = classification.agent

    if agent == "portfolio_health":
        from src.agents.portfolio_health import run

        focus_tickers = classification.entities_dict().get("tickers")
        return run(
            user=user, client=client, model=model,
            query=query, history=history, focus_tickers=focus_tickers,
        )

    return {
        "status": "not_implemented",
        "intent": classification.intent,
        "agent": agent,
        "entities": classification.entities_dict(),
        "message": f"The {agent} agent is not implemented in this build.",
    }
