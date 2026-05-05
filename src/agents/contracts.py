from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.agents.catalog import AgentName


class AgentMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0


class AgentRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    agent: AgentName
    intent: str
    entities: dict[str, Any] = Field(default_factory=dict)
    user: dict[str, Any] | None = None
    client: Any
    model: str | None = None
    query: str | None = None
    history: list[dict[str, str]] | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="allow", use_enum_values=True)

    status: Literal["ok", "not_implemented"]
    agent: AgentName
    intent: str | None = None
    entities: dict[str, Any] | None = None
    message: str | None = None
    observations: list[dict[str, Any]] | None = None
    concentration_risk: dict[str, Any] | None = None
    performance: dict[str, Any] | None = None
    benchmark_comparison: dict[str, Any] | None = None
    disclaimer: str | None = None
    _meta: AgentMeta | None = None

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


AgentHandler = Callable[[AgentRequest], AgentResponse]
