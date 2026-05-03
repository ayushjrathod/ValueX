from openai import OpenAI

from src.config.settings import get_settings


settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

