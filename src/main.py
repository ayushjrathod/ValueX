import asyncio
import logging
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.classifier.classifier import ClassificationError, ClassificationRefusal, classify
from src.config import get_settings
from src.router import route
from src.safety.guard import check, warm_load as warm_safety_model
from src.session import get_session_store
from src.users import get_user, list_users
from src.utils.llm import get_client
from src.utils.tracking import track_and_log_metrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    user_id: str | None = None
    session_id: str | None = None


class UserSummaryResponse(BaseModel):
    summary: str = Field(..., min_length=1)


async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    warm_safety_model()
    logger.info("Safety classifier warmed.")
    yield
    logger.info("Shutting down...")
    logger.info("Shutdown complete.")


app = FastAPI(
    title="ValueX Agents API",
    description="API for ValueX financial agents",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins: list[str] = []

if settings.is_development:
    allowed_origins.extend(
        [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
    )
# Allow all origins in production for now — restrict to specific domains before real deployment
if settings.is_production:
    allowed_origins.extend(
        [
            "*"
        ]
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return JSONResponse(
        content={
            "status": "success",
            "status_code": 200,
            "message": "Welcome to the ValueX Agents API!",
        }
    )

@app.get("/health")
async def health():
    return JSONResponse(
        content={
            "status": "success",
            "status_code": 200,
            "message": "API is healthy!",
        }
    )


@app.get("/users")
async def users():
    return JSONResponse(
        content={
            "status": "success",
            "status_code": 200,
            "users": list_users(),
        }
    )


@app.get("/user-summary")
async def user_summary(user_id: str):
    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"Unknown user_id: {user_id}")

    try:
        llm_client = get_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    summary = await asyncio.to_thread(_summarize_user, user, llm_client)
    return JSONResponse(
        content={
            "status": "success",
            "status_code": 200,
            "user_id": user_id,
            "summary": summary,
        }
    )


@app.post("/chat")
async def chat(request: ChatRequest):
    return EventSourceResponse(stream_chat_response(request))


async def stream_chat_response(request: ChatRequest) -> AsyncIterator[dict[str, str]]:
    session_store = get_session_store()
    t_start = time.perf_counter()
    deadline = t_start + settings.pipeline_timeout_s
    metrics: dict[str, Any] = {}
    t_first_emit: float | None = None

    try:
        # ---- Safety guard (sync, <10 ms) ----
        verdict = check(request.query)
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
                "user_id": request.user_id,
                "session_id": request.session_id,
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
            session_store.get_history(request.session_id)
            if request.session_id
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
                    request.query,
                    client=llm_client,
                    session_history=history or None,
                ),
                timeout=remaining,
            )
        except asyncio.TimeoutError:
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

        user = get_user(request.user_id) if request.user_id else None
        if request.user_id and user is None:
            yield sse_event("error", {
                "message": "We couldn't find your user account. Please check your user_id and try again.",
                "code": "user_not_found",
                "user_id": request.user_id,
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
                    query=request.query,
                    history=history,
                ),
                timeout=remaining,
            )
        except asyncio.TimeoutError:
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
            user_id=request.user_id,
        )

        # Persist the sanitized agent payload, not internal observability metadata.
        if request.session_id:
            session_store.add_turn(
                request.session_id, request.query, agent_response,
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


def _summarize_user(user: dict[str, Any], llm_client: Any) -> str:
    positions = user.get("positions", [])
    top_holdings = ", ".join(position.get("ticker", "?") for position in positions[:5]) or "none"
    prompt = "\n".join(
        [
            f"name: {user.get('name', 'Unknown')}",
            f"country: {user.get('country', 'N/A')}",
            f"risk_profile: {user.get('risk_profile', 'N/A')}",
            f"base_currency: {user.get('base_currency', 'N/A')}",
            f"positions_count: {len(positions)}",
            f"preferred_benchmark: {user.get('preferences', {}).get('preferred_benchmark', 'N/A')}",
            f"top_holdings: {top_holdings}",
        ]
    )

    response = llm_client.responses.parse(
        model=settings.openai_model,
        input=[
            {
                "role": "system",
                "content": (
                    "Write a concise, customer-facing summary of a fixture investor profile. "
                    "Keep it to 2 sentences, plain English, no bullet points, and mention risk posture and portfolio shape."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        store=False,
        text_format=UserSummaryResponse,
    )

    parsed = getattr(response, "output_parsed", None)
    if parsed is not None:
        result = UserSummaryResponse.model_validate(parsed)
        return result.summary

    raise RuntimeError("Could not parse user summary response.")


if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=settings.api_port)
