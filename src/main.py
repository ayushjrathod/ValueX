import logging
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.classifier.classifier import ClassificationError, ClassificationRefusal, classify
from src.config import get_settings
from src.router import route
from src.safety.gaurd import check
from src.users import get_user
from src.utils.llm import client as llm_client

# set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    user_id: str | None = None
    session_id: str | None = None


async def lifespan(app: FastAPI):
    # add db connect here
    logger.info("Starting up...")
    yield
    logger.info("Shutting down...")
    # add db disconnect here
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Valura AI Agents API",
    description="API for Valura AI Agents",
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
# Allow all origins in production for now, but this should be restricted to specific domains in production
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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
    expose_headers=["*"],
)

@app.get("/")
async def root():
  return JSONResponse(content={"status": "success", "status_code": 200, "message": "Welcome to the Valura AI Agents API!"})

@app.get("/health")
async def health():
  return JSONResponse(content={"status": "success", "status_code": 200, "message": "API is healthy!"})


@app.post("/chat")
async def chat(request: ChatRequest):
    return EventSourceResponse(stream_chat_response(request))


async def stream_chat_response(request: ChatRequest) -> AsyncIterator[dict[str, str]]:
    try:
        # 1. Safety guard
        verdict = check(request.query)
        logger.info(
            "Safety guard verdict: blocked=%s category=%s",
            verdict.blocked,
            verdict.category,
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
            yield sse_event("done", {"status": "blocked"})
            return

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
        # 2. Classify and route
        classification = classify(request.query, client=llm_client)
        entities = classification.entities_dict()
        logger.info(
            "Classifier routed query: agent=%s entities=%s",
            classification.agent,
            entities,
        )
        yield sse_event(
            "metadata",
            {
                "stage": "classifier",
                "status": "routed",
                "agent": classification.agent,
                "entities": entities,
            },
        )

        user = get_user(request.user_id) if request.user_id else None

        agent_response = route(
            classification,
            user=user,
            client=llm_client,
        )
        yield sse_event("message", agent_response)
        yield sse_event("done", {"status": "ok"})
        
    except ClassificationRefusal as exc:
        logger.warning("Classifier refused request: %s", exc)
        error_msg, error_code = "Classifier refused to process the request.", "classification_refused"
    except ClassificationError:
        logger.exception("Classifier failed to parse the OpenAI response")
        error_msg, error_code = "Request failed while classifying the query.", "classification_error"
    except Exception:
        logger.exception("Unhandled error while streaming chat response")
        error_msg, error_code = "Request failed while processing the AI pipeline.", "internal_error"

    if 'error_msg' in locals():
        yield sse_event("error", {"message": error_msg, "code": error_code})


def sse_event(event: str, data: dict) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data)}


if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=8000)
