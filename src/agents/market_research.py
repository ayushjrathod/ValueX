from src.agents.catalog import AgentName
from src.agents.contracts import AgentRequest, AgentResponse


def run(request: AgentRequest) -> AgentResponse:
	return AgentResponse(
		status="not_implemented",
		intent=request.intent,
		agent=AgentName.MARKET_RESEARCH,
		entities=request.entities,
		message="The market_research agent is registered, but its research workflow is not implemented in this build.",
	)
