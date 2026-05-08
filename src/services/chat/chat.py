import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from collections.abc import Callable
from typing import Any

from src.agents.catalog import AgentName
from src.agents.contracts import AgentRequest
from src.agents.general_query import run as run_general_query
from src.agents.router import route
from src.config import get_settings
from src.services.chat.models import ChatRequest
from src.services.classifier.classifier import ClassificationError, ClassificationRefusal, classify
from src.services.safety import check
from src.utils.llm import get_client
from src.utils.session import get_session_store
from src.utils.tracking import track_and_log_metrics
from src.utils.users import get_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


async def stream_chat_response(
    request: ChatRequest,
    *,
    get_client_fn: Callable[[], Any] = get_client,
    classify_fn: Callable[..., Any] = classify,
    route_fn: Callable[..., dict[str, Any]] = route,
) -> AsyncIterator[dict[str, str]]:
    query = request.query
    user_id = request.user_id
    session_id = request.session_id

    session_store = get_session_store()
    t_start = time.perf_counter()
    metrics: dict[str, Any] = {}
    t_first_emit: float | None = None

    try:
        # ---- Safety guard (sync, <10 ms) ----
        verdict = check(query)
        t_safety = time.perf_counter()
        metrics["safety_ms"] = round(
            (t_safety - t_start) * 1000
        )
        logger.info(
            "Safety guard verdict: blocked=%s category=%s (%dms)",
            verdict.blocked,
            verdict.category,
            metrics["safety_ms"],
        )
        if verdict.blocked:
            yield sse_event(
                "safety_blocked",
                {
                    "blocked": True,
                    "category": verdict.category,
                    "message": verdict.message,
                },
            )
            # termination signal
            yield sse_event("done", {"status": "blocked"})
            return

        t_first_emit = time.perf_counter()
        yield sse_event(
            "metadata",
            {
                "stage": "safety_guard",
                "status": "passed",
                "blocked": False,
                "user_id": user_id,
                "session_id": session_id,
            },
        )
        # Ensure LLM client is available
        try:
            llm_client = get_client_fn()
        except RuntimeError:
            yield sse_event("error", {
                "message": "LLM service unavailable. API_KEY is not configured.",
                "code": "llm_unavailable",
            })
            yield sse_event("done", {"status": "error"})
            return

        history = (
            session_store.get_history(session_id)
            if session_id
            else []
        )

        classification = await asyncio.to_thread(
            classify_fn,
            query,
            client=llm_client,
            session_history=history or None,
        )

        t_classify = time.perf_counter()
        metrics["classifier_ms"] = round(
            (t_classify - t_safety) * 1000
        )

        entities = classification.entities_dict()
        logger.info(
            "Classifier routed query: agent=%s entities=%s (%dms)",
            classification.agent,
            entities,
            metrics["classifier_ms"],
        )
        yield sse_event(
            "metadata",
            {
                "stage": "classifier",
                "status": "routed",
                "intent": classification.intent,
                "agent": classification.agent,
                "entities": entities,
                "safety_verdict": classification.safety_verdict,
            },
        )

        user = get_user(user_id) if user_id else None
        if user_id and user is None:
            yield sse_event("error", {
                "message": "We couldn't find your user account. Please check your user_id and try again.",
                "code": "user_not_found",
                "user_id": user_id,
            })
            yield sse_event("done", {"status": "error"})
            return

        yield sse_event(
            "progress",
            {"stage": "agent_dispatch", "agent": classification.agent},
        )

        if classification.agent == AgentName.GENERAL_QUERY:
            agent_request = AgentRequest(
                agent=classification.agent,
                intent=classification.intent,
                entities=classification.entities_dict(),
                user=user,
                client=llm_client,
                query=query,
                history=history,
            )
            agent = await asyncio.to_thread(run_general_query, agent_request)
            agent_response = agent.to_payload()
        else:
            agent_response = await asyncio.to_thread(
                route_fn,
                classification,
                user=user,
                client=llm_client,
                query=query,
                history=history,
            )

        t_agent = time.perf_counter()
        metrics["agent_ms"] = round(
            (t_agent - t_classify) * 1000
        )

        # Structured log + metrics dict for the SSE `metrics` event.
        # `first_message_ms` measures the first SSE event the client sees,
        t_end = time.perf_counter()
        metrics["first_message_ms"] = round(
            ((t_first_emit or t_end) - t_start) * 1000
        )
        track_and_log_metrics(
            agent_response=agent_response,
            classification=classification,
            metrics=metrics,
            t_start=t_start,
            t_classify=t_classify,
            t_agent=t_agent,
            t_end=t_end,
            settings=settings,
            user_id=user_id,
        )

        # Persist the sanitized agent payload, not internal observability metadata.
        if session_id:
            session_store.add_turn(
                session_id, query, agent_response,
            )

        yield sse_event("message", agent_response)
        yield sse_event("metrics", metrics)
        yield sse_event("done", {"status": "ok"})

    except ClassificationRefusal as exc:
        logger.warning("Classifier refused request: %s", exc)
        yield sse_event("error", {"message": "Classifier refused to process the request.", "code": "classification_refused"})
        yield sse_event("done", {"status": "error"})
    except ClassificationError:
        logger.exception("Classifier failed to parse the OpenAI response")
        yield sse_event("error", {"message": "Request failed while classifying the query.", "code": "classification_error"})
        yield sse_event("done", {"status": "error"})
    except Exception:
        logger.exception("Unhandled error while streaming chat response")
        yield sse_event("error", {"message": "Internal error.", "code": "internal_error"})
        yield sse_event("done", {"status": "error"})


def sse_event(event: str, data: dict) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data)}
