from typing import Any

from pydantic import BaseModel, Field

from src.config import get_settings


class UserSummaryResponse(BaseModel):
    summary: str = Field(..., min_length=1)


def summarize_user(user: dict[str, Any], llm_client: Any) -> str:
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
    settings = get_settings()
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

