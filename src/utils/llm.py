from openai import OpenAI

from src.config.settings import get_settings


settings = get_settings()
client: OpenAI | None = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None


def get_client() -> OpenAI:
    """Return the OpenAI client, raising a clear error if no API key is configured."""
    if client is None:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Configure it in .env to use LLM features."
        )
    return client

