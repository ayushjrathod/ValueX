import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings

# set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


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

if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=8000)