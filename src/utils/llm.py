from typing import Any

from openai import OpenAI
from pydantic import BaseModel

from src.config.settings import get_settings


class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

class _ParsedResponse:
    def __init__(self, parsed: BaseModel, usage: _Usage | None = None):
        self.output_parsed = parsed
        self.usage = usage

class _GeminiResponses:
    def __init__(self, client: Any, settings: Any):
        self._client = client
        self._settings = settings

    def parse(self, model: str, input: list[dict[str, str]], store: bool = False, temperature: float = 0.0, text_format: Any = None) -> _ParsedResponse:
        from google.genai import types
        
        contents = []
        system_instruction = None
        for msg in input:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            else:
                gemini_role = "model" if role == "assistant" else "user"
                contents.append(types.Content(role=gemini_role, parts=[types.Part.from_text(text=content)]))

        config_args: dict[str, Any] = {
            "temperature": temperature,
        }
        if system_instruction:
            config_args["system_instruction"] = system_instruction
        
        if text_format is not None:
            config_args["response_mime_type"] = "application/json"
            config_args["response_schema"] = text_format

        config = types.GenerateContentConfig(**config_args)
        
        gemini_model = self._settings.gemini_model_id
            
        response = self._client.models.generate_content(
            model=gemini_model,
            contents=contents,
            config=config,
        )

        parsed_obj = None
        if text_format is not None and response.text:
            parsed_obj = text_format.model_validate_json(response.text)

        usage = None
        if response.usage_metadata:
            usage = _Usage(
                input_tokens=response.usage_metadata.prompt_token_count,
                output_tokens=response.usage_metadata.candidates_token_count,
            )

        return _ParsedResponse(parsed=parsed_obj, usage=usage)

class GeminiGCPClient:
    def __init__(self, project: str, location: str):
        from google import genai
        self._client = genai.Client(vertexai=True, project=project, location=location)
        self.responses = _GeminiResponses(self._client, get_settings())


_openai_client = None
_gcp_client = None

def get_client() -> Any:
    """Return the LLM client configured by the settings."""
    settings = get_settings()
    
    if settings.llm == "gcp":
        global _gcp_client
        if _gcp_client is None:
            if not settings.google_cloud_project:
                raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set. Configure it in .env to use GCP LLM.")
            _gcp_client = GeminiGCPClient(project=settings.google_cloud_project, location=settings.google_cloud_region)
        return _gcp_client
    else:
        global _openai_client
        if _openai_client is None:
            if not settings.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is not set. Configure it in .env to use LLM features.")
            _openai_client = OpenAI(api_key=settings.openai_api_key)
        return _openai_client
