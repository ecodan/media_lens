import json
import logging
import os
import traceback
from pathlib import Path
from typing import List, Dict

import dotenv
from anthropic import APIError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.media_lens.common import LOGGER_NAME, get_project_root, ANTHROPIC_MODEL
from src.media_lens.extraction.agent import Agent, ClaudeLLMAgent

logger = logging.getLogger(LOGGER_NAME)

SYSTEM_PROMPT: str = """
You are a skilled media analyst and sociologist. You'll be given several news articles and then asked questions
about the content of the articles and what might be deduced from them.
"""

REASONING_PROMPT: str = """
Step back, analyze this news content and answer the following questions:
- What is the most important news right now?
- What are biggest issues in the world right now?
- For articles referring to the president of the U.S. (Donald Trump), is the president is doing a [poor, ok, good, excellent] job based on the portrayal.
- What are three adjectives that best describe the situation in the U.S.
- What are three adjectives that best describe the job performance and character of the U.S. President.

You will format your response as a JSON object containing question and answer.

Format your response EXACTLY as a JSON object with this structure, and only this structure:
[
{{
"question": "<question as written above>",
"answer": "<your answer, as text>"
}}
...
]

<content>
{content}
</content>

Respond ONLY with JSON and no other text.

RESPONSE: 
"""

class LLMWebsiteInterpreter:
    """
    Class to interpret and answer questions about the content of a website using a large language model (LLM).
    """
    def __init__(self, agent: Agent):
        self.agent: Agent = agent

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=lambda e: isinstance(e, (APIError, APIConnectionError))
    )
    def _call_llm(self, user_prompt: str, system_prompt: str) -> str:
        return self.agent.infer(system_prompt=system_prompt, user_prompt=user_prompt)


    def interpret_from_files(self, files: List[Path]) -> List:
        """
        Convenience method to create a concatenated list of articles from a list of files.
        :param files: list of files to read and concatenate
        :return:
        """
        logger.info(f"Interpreting {len(files)} files")
        content: List[Dict] = []
        for file in files:
            with open(file, "rb") as f:
                article: dict = json.load(f)
                content.append(article)
        return self.interpret(content)

    def interpret(self, content: list) -> List:
        """
        Interpret the content of a website using a large language model (LLM).
        :param content: all of the content to interpret
        :return: a list of question and answer pairs
        """
        logger.debug(f"Interpreting content: {len(content)} bytes")
        try:
            payload = [
                f"<article>TITLE: {element['title']}\nTEXT: {element['text']}\n</article>\n" for element in content
            ]

            response: str = self._call_llm(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=REASONING_PROMPT.format(
                    content=payload
                )
            )
            content = json.loads(response)
            return content

        except Exception as e:
            logger.error(f"Error extracting news content: {str(e)}")
            print(traceback.format_exc())
            return []

##########################
# TEST
def main(working_dir: Path, site: str):
    agent: Agent = ClaudeLLMAgent(api_key=os.getenv("ANTHROPIC_API_KEY"), model=ANTHROPIC_MODEL)
    interpreter = LLMWebsiteInterpreter(agent=agent)
    files = [f for f in working_dir.glob(f"{site}-clean-article-*.json")]
    print(json.dumps(interpreter.interpret_from_files(files), indent=2))

if __name__ == '__main__':
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    main(Path(get_project_root() / "working/out/2025-02-22T20:49:31+00:00"), "www.bbc.com")