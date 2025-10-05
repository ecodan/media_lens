import logging
import os
from abc import ABCMeta, abstractmethod
from typing import Optional

from anthropic import Anthropic, APIStatusError, APIConnectionError

try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    VERTEX_AI_AVAILABLE = True
except ImportError:
    vertexai = None
    GenerativeModel = None
    VERTEX_AI_AVAILABLE = False

from src.media_lens.common import LOGGER_NAME, AI_PROVIDER, ANTHROPIC_MODEL, VERTEX_AI_PROJECT_ID, VERTEX_AI_LOCATION, VERTEX_AI_MODEL

logger = logging.getLogger(LOGGER_NAME)

class Agent(metaclass=ABCMeta):
    """
    Base class for all agents.
    """
    @abstractmethod
    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send the prompts to the LLM and return the response.
        :param system_prompt: generated system prompt
        :param user_prompt: specific user prompt
        :return: text of response
        """
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """
        Return the model name.
        :return: model name
        """
        pass


class ClaudeLLMAgent(Agent):
    """
    Anthropic Claude LLM agent.
    """
    def __init__(self, api_key: str, model: str):
        super().__init__()
        self.client = Anthropic(api_key=api_key)
        self._model = model

    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )
            logger.debug(f"Claude raw response: {response.content}")
            if len(response.content) == 1:
                logger.debug(f".. response: {len(response.content[0].text)} bytes / {len(response.content[0].text.split())} words")
                return response.content[0].text
            else:
                return "ERROR - NO DATA"
        except (APIStatusError, APIConnectionError) as e:
            logger.error(f"Claude API error: {str(e)}")
            raise

    @property
    def model(self) -> str:
        return self._model


class GoogleVertexAIAgent(Agent):
    """
    Google Vertex AI LLM agent.
    """
    def __init__(self, project_id: str, location: str, model: str):
        super().__init__()
        if not VERTEX_AI_AVAILABLE:
            raise ImportError("google-cloud-aiplatform package is required for Google Vertex AI support")
        
        vertexai.init(project=project_id, location=location)
        self.client = GenerativeModel(model)
        self._model = model

    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        try:
            # Combine system and user prompts for Vertex AI
            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            response = self.client.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 20000,  # Increased from 4096, still well under 64K limit
                }
            )

            # Handle multi-part responses (e.g., when model uses <thinking> tags)
            # Vertex AI may split response into multiple parts
            try:
                # Try to get text directly first
                response_text = response.text
            except ValueError:
                # If that fails, concatenate all text parts manually
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        text_parts = [part.text for part in candidate.content.parts if hasattr(part, 'text')]
                        response_text = ''.join(text_parts)
                    else:
                        raise ValueError("Unable to extract text from Vertex AI response")
                else:
                    raise ValueError("Unable to extract text from Vertex AI response")

            logger.debug(f"Vertex AI raw response: {response_text}")
            logger.debug(f".. response: {len(response_text)} bytes / {len(response_text.split())} words")

            return response_text

        except Exception as e:
            logger.error(f"Vertex AI API error: {str(e)}")
            raise

    @property
    def model(self) -> str:
        return self._model


class OllamaAgent(Agent):
    """
    Local Ollama LLM agent.
    """

    def __init__(self, model_version: str):
        super().__init__()
        self._model_version = model_version
        self._base_url: str = "http://localhost:11434"
        self._api_url = f"{self._base_url}/api/generate"

    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        try:
            """
             Send the prompts to Ollama and return the response.

             :param user_prompt: Specific user prompt
             :param system_prompt: Optional system prompt override. If None, loads from config via prompt manager.
             :param history: Optional conversation history for context
             :return: Text of response
             """
            import requests
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            # Prepare the request payload
            payload = {
                "model": self._model_version,
                "prompt": full_prompt,
                "stream": False
            }
            response = requests.post(
                self._api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            # Parse the response
            response_data = response.json()

            logger.debug(f"Ollama raw response: {response_data}")

            if "response" in response_data:
                response_text = response_data["response"]
                logger.debug(
                    f".. response: {len(response_text)} bytes / {len(response_text.split())} words"
                )

                # Prepare response data for logging
                response_log_data = {
                    "content": response_text,
                    "tokens_used": {
                        "input": response_data.get("eval_count"),
                        "output": response_data.get("prompt_eval_count"),
                    },
                }

                return response_text
            else:
                error_response = "ERROR - NO DATA"
                return error_response
        except Exception as e:
            logger.error(f"Ollama API error: {str(e)}")

    @property
    def model(self) -> str:
        return self._model_version


def create_agent(provider: str = "claude", **kwargs) -> Agent:
    """
    Factory function to create an agent instance based on provider.
    
    :param provider: The AI provider ("claude" or "vertex")
    :param kwargs: Provider-specific configuration parameters
    :return: Agent instance
    """
    if provider.lower() == "claude":
        api_key = kwargs.get("api_key")
        model = kwargs.get("model", "claude-3-5-haiku-latest")
        
        if not api_key:
            raise ValueError("api_key is required for Claude provider")
        
        return ClaudeLLMAgent(api_key=api_key, model=model)
    
    elif provider.lower() == "vertex":
        project_id = kwargs.get("project_id")
        location = kwargs.get("location", "us-central1")
        model = kwargs.get("model", "gemini-2.5-flash")
        
        if not project_id:
            raise ValueError("project_id is required for Vertex AI provider")
        
        return GoogleVertexAIAgent(project_id=project_id, location=location, model=model)
    elif provider.lower() == "ollama":
        model = kwargs.get("model")
        return OllamaAgent(model_version=model)
    else:
        raise ValueError(f"Unsupported provider: {provider}. Supported providers: claude, vertex")


def create_agent_from_env() -> Agent:
    """
    Create an agent instance using environment variables and common configuration.
    
    :return: Agent instance configured from environment
    """
    # Ensure secrets are loaded before creating the agent
    from src.media_lens.common import ensure_secrets_loaded
    loaded_secrets = ensure_secrets_loaded()
    
    provider = os.getenv("AI_PROVIDER", AI_PROVIDER).lower()
    
    if provider == "claude":
        # Try environment variable first, then fall back to loaded secrets
        api_key = os.getenv("ANTHROPIC_API_KEY") or loaded_secrets.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error(f"ANTHROPIC_API_KEY not found in environment or loaded secrets")
            logger.error(f"Environment keys: {list(k for k in os.environ.keys() if 'ANTHROPIC' in k)}")
            logger.error(f"Loaded secrets: {list(loaded_secrets.keys())}")
            logger.error(f"ANTHROPIC_API_KEY from secrets: {loaded_secrets.get('ANTHROPIC_API_KEY') is not None}")
            raise ValueError("ANTHROPIC_API_KEY environment variable is required for Claude provider")
        
        model = os.getenv("ANTHROPIC_MODEL", ANTHROPIC_MODEL)
        return create_agent(provider="claude", api_key=api_key, model=model)
    
    elif provider == "vertex":
        project_id = os.getenv("VERTEX_AI_PROJECT_ID", VERTEX_AI_PROJECT_ID)
        if not project_id:
            raise ValueError("VERTEX_AI_PROJECT_ID environment variable is required for Vertex AI provider")
        
        location = os.getenv("VERTEX_AI_LOCATION", VERTEX_AI_LOCATION)
        model = os.getenv("VERTEX_AI_MODEL", VERTEX_AI_MODEL)
        return create_agent(provider="vertex", project_id=project_id, location=location, model=model)
    elif provider == "ollama":
        model = os.getenv("OLLAMA_MODEL_VERSION")
        return create_agent(provider="ollama", model=model)
    else:
        return create_agent(provider=provider)  # Let create_agent handle the error