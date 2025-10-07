import logging
import os
import re
from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Optional

import litellm

from src.media_lens.common import LOGGER_NAME, DEFAULT_AI_PROVIDER, ANTHROPIC_MODEL, VERTEX_AI_PROJECT_ID, VERTEX_AI_LOCATION, VERTEX_AI_MODEL

logger = logging.getLogger(LOGGER_NAME)


class ResponseFormat(Enum):
    """Response format types for agent invocation."""
    TEXT = "text"
    JSON = "json"


class Agent(metaclass=ABCMeta):
    """
    Base class for all agents.
    """

    @abstractmethod
    def _invoke_impl(self, system_prompt: str, user_prompt: str, response_format: Optional[ResponseFormat] = None) -> str:
        """
        Implementation-specific invoke method.
        :param system_prompt: generated system prompt
        :param user_prompt: specific user prompt
        :param response_format: expected response format (TEXT or JSON)
        :return: text of response
        """
        pass

    def invoke(self, system_prompt: str, user_prompt: str, response_format: ResponseFormat = ResponseFormat.TEXT) -> str:
        """
        Send the prompts to the LLM and return the response.
        :param system_prompt: generated system prompt
        :param user_prompt: specific user prompt
        :param response_format: expected response format (TEXT or JSON)
        :return: text of response, cleaned according to response_format
        """
        response = self._invoke_impl(system_prompt, user_prompt, response_format)

        # Still apply cleaning for JSON responses to handle edge cases and legacy providers
        if response_format == ResponseFormat.JSON:
            return self._clean_json_response(response)

        return response

    def _clean_json_response(self, response: str) -> str:
        """
        Clean JSON response by removing markdown fences and extraction tags.
        :param response: raw response text
        :return: cleaned JSON string
        """
        response = response.strip()

        # Extract from thinking/analysis tags if present
        if "</thinking>" in response:
            match = re.search(r"</thinking>(.*)", response, re.DOTALL)
            if match:
                response = match.group(1).strip()

        if "</analysis>" in response:
            match = re.search(r"</analysis>(.*)", response, re.DOTALL)
            if match:
                response = match.group(1).strip()

        # Extract from output tags if present
        if "<output>" in response and "</output>" in response:
            match = re.search(r"<output>(.*?)</output>", response, re.DOTALL)
            if match:
                response = match.group(1).strip()

        # Strip markdown code fences
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]

        if response.endswith("```"):
            response = response[:-3]

        response = response.strip()

        # If response still doesn't start with { or [, try to extract JSON
        if not response.startswith('{') and not response.startswith('['):
            # Look for first occurrence of { or [
            json_start = min(
                (response.find('{') if response.find('{') != -1 else len(response)),
                (response.find('[') if response.find('[') != -1 else len(response))
            )
            if json_start < len(response):
                response = response[json_start:]

        return response.strip()

    @property
    @abstractmethod
    def model(self) -> str:
        """
        Return the model name.
        :return: model name
        """
        pass


class LiteLLMAgent(Agent):
    """
    Unified LLM agent using LiteLLM for provider-agnostic access.
    Supports Anthropic Claude, Google Vertex AI, Ollama, and 100+ other providers.
    """
    def __init__(self, model: str, **kwargs):
        """
        Initialize LiteLLM agent.

        :param model: Model identifier in LiteLLM format
                     Examples:
                     - "anthropic/claude-sonnet-4-5"
                     - "vertex_ai/gemini-2.5-flash"
                     - "ollama/qwen"
        :param kwargs: Additional provider-specific parameters
                      For Vertex AI:
                      - vertex_project: GCP project ID
                      - vertex_location: GCP region
        """
        super().__init__()
        self._model = model
        self._kwargs = kwargs

    def _invoke_impl(self, system_prompt: str, user_prompt: str, response_format: Optional['ResponseFormat'] = None) -> str:
        """
        Invoke LiteLLM completion API.

        :param system_prompt: System prompt
        :param user_prompt: User prompt
        :param response_format: Expected response format (TEXT or JSON)
        :return: Response text
        """
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # Build completion kwargs
            completion_kwargs = {
                "model": self._model,
                "messages": messages,
                "temperature": 0,
                "max_tokens": 4096,
                **self._kwargs
            }

            # Add native JSON mode if requested
            if response_format == ResponseFormat.JSON:
                completion_kwargs["response_format"] = {"type": "json_object"}

            response = litellm.completion(**completion_kwargs)

            response_text = response.choices[0].message.content
            logger.debug(f"LiteLLM raw response: {response_text}")
            logger.debug(f".. response: {len(response_text)} bytes / {len(response_text.split())} words")

            return response_text

        except Exception as e:
            logger.error(f"LiteLLM API error: {str(e)}")
            raise

    @property
    def model(self) -> str:
        return self._model


def create_agent(provider: str = "claude", **kwargs) -> Agent:
    """
    Factory function to create an agent instance based on provider.

    :param provider: The AI provider ("claude", "vertex", or "ollama")
    :param kwargs: Provider-specific configuration parameters
    :return: Agent instance
    """
    if provider.lower() == "claude":
        model = kwargs.get("model", "claude-3-5-haiku-latest")
        # LiteLLM uses ANTHROPIC_API_KEY from environment
        litellm_model = f"anthropic/{model}"
        return LiteLLMAgent(model=litellm_model)

    elif provider.lower() == "vertex":
        project_id = kwargs.get("project_id")
        location = kwargs.get("location", "us-central1")
        model = kwargs.get("model", "gemini-2.5-flash")

        if not project_id:
            raise ValueError("project_id is required for Vertex AI provider")

        litellm_model = f"vertex_ai/{model}"
        return LiteLLMAgent(
            model=litellm_model,
            vertex_project=project_id,
            vertex_location=location
        )

    elif provider.lower() == "ollama":
        model = kwargs.get("model", "qwen")
        litellm_model = f"ollama/{model}"
        return LiteLLMAgent(model=litellm_model)

    else:
        raise ValueError(f"Unsupported provider: {provider}. Supported providers: claude, vertex, ollama")


def create_agent_from_env() -> Agent:
    """
    Create an agent instance using environment variables and common configuration.

    :return: Agent instance configured from environment
    """
    # Ensure secrets are loaded before creating the agent
    from src.media_lens.secret_manager import load_secrets_from_gcp
    loaded_secrets = load_secrets_from_gcp()

    provider = os.getenv("AI_PROVIDER", DEFAULT_AI_PROVIDER).lower()

    if provider == "claude":
        # Try environment variable first, then fall back to loaded secrets
        api_key = os.getenv("ANTHROPIC_API_KEY") or loaded_secrets.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error(f"ANTHROPIC_API_KEY not found in environment or loaded secrets")
            logger.error(f"Environment keys: {list(k for k in os.environ.keys() if 'ANTHROPIC' in k)}")
            logger.error(f"Loaded secrets: {list(loaded_secrets.keys())}")
            raise ValueError("ANTHROPIC_API_KEY environment variable is required for Claude provider")

        # Set API key for LiteLLM
        os.environ["ANTHROPIC_API_KEY"] = api_key

        model = os.getenv("ANTHROPIC_MODEL", ANTHROPIC_MODEL)
        return create_agent(provider="claude", model=model)

    elif provider == "vertex":
        project_id = os.getenv("VERTEX_AI_PROJECT_ID", VERTEX_AI_PROJECT_ID)
        if not project_id:
            raise ValueError("VERTEX_AI_PROJECT_ID environment variable is required for Vertex AI provider")

        location = os.getenv("VERTEX_AI_LOCATION", VERTEX_AI_LOCATION)
        model = os.getenv("VERTEX_AI_MODEL", VERTEX_AI_MODEL)
        return create_agent(provider="vertex", project_id=project_id, location=location, model=model)

    elif provider == "ollama":
        model = os.getenv("OLLAMA_MODEL_VERSION", "qwen")
        return create_agent(provider="ollama", model=model)

    else:
        raise ValueError(f"Unsupported provider: {provider}. Supported providers: claude, vertex, ollama")
