import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from src.agents.router import route
from src.config import get_settings
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
    query: str,
    user_id: str | None = None,
    session_id: str | None = None,
) -> AsyncIterator[dict[str, str]]:
    session_store = get_session_store()
    t_start = time.perf_counter()
    deadline = t_start + settings.pipeline_timeout_s
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
            t_first_emit = time.perf_counter()
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
            llm_client = get_client()
        except RuntimeError:
            yield sse_event("error", {
                "message": "LLM service unavailable. OPENAI_API_KEY is not configured.",
                "code": "llm_unavailable",
            })
            yield sse_event("done", {"status": "error"})
            return

        history = (
            session_store.get_history(session_id)
            if session_id
            else []
        )

        # Classifier (LLM call — run in thread with timeout) 
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            yield _timeout_event(time.perf_counter() - t_start)
            yield sse_event("done", {"status": "error"})
            return

        try:
            classification = await asyncio.wait_for(
                asyncio.to_thread(
                    classify,
                    query,
                    client=llm_client,
                    session_history=history or None,
                ),
                timeout=remaining,
            )
        except TimeoutError:
            yield _timeout_event(time.perf_counter() - t_start)
            yield sse_event("done", {"status": "error"})
            return

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

        # Agent dispatch (LLM + tools — run in thread with remaining budget) 
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            yield _timeout_event(time.perf_counter() - t_start)
            yield sse_event("done", {"status": "error"})
            return

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

        try:
            agent_response = await asyncio.wait_for(
                asyncio.to_thread(
                    route,
                    classification,
                    user=user,
                    client=llm_client,
                    query=query,
                    history=history,
                ),
                timeout=remaining,
            )
        except TimeoutError:
            yield _timeout_event(time.perf_counter() - t_start)
            yield sse_event("done", {"status": "error"})
            return

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


def _timeout_event(elapsed_s: float) -> dict[str, str]:
    logger.warning(
        "Pipeline timeout after %.1fs (limit %.1fs)",
        elapsed_s,
        settings.pipeline_timeout_s,
    )
    return sse_event(
        "error",
        {
            "message": f"Request timed out after {settings.pipeline_timeout_s:.0f}s. Please try again.",
            "code": "pipeline_timeout",
            "elapsed_s": round(elapsed_s, 2),
        },
    )


def sse_event(event: str, data: dict) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data)}
