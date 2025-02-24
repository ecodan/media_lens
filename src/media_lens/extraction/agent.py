import logging
from abc import ABCMeta

from anthropic import Anthropic

from src.media_lens.common import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

class Agent(metaclass=ABCMeta):
    """
    Base class for all agents.
    """

    def infer(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send the prompts to the LLM and return the response.
        :param system_prompt: generated system prompt
        :param user_prompt: specific user prompt
        :return: text of response
        """
        pass


class ClaudeLLMAgent(Agent):
    """
    Anthropic Claude LLM agent.
    """
    def __init__(self, api_key: str, model: str):
        super().__init__()
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def infer(self, system_prompt: str, user_prompt: str) -> str:
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
        logger.debug(f".. response: {len(response.content)} bytes / {len(response.content)} words")
        logger.debug(f"Claude raw response: {response.content}")
        if len(response.content) == 1:
            return response.content[0].text
        else:
            return "ERROR - NO DATA"