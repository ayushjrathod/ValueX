import asyncio
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from src.config import get_settings
from src.services.chat.models import ChatRequest
from src.services.chat.chat import stream_chat_response
from src.services.safety.guard import warm_load as warm_safety_model
from src.services.user_summary.user_summary import summarize_user
from src.utils.llm import get_client
from src.utils.users import get_user, list_users

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


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

    summary = await asyncio.to_thread(summarize_user, user, llm_client)
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
    return EventSourceResponse(
        stream_chat_response(request)
    )

if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=settings.api_port)
