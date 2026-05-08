from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    user_id: str | None = None
    session_id: str | None = None
