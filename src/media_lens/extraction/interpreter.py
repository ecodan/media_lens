import json
import logging
import os
import traceback
from logging import Logger
from pathlib import Path
from typing import List, Dict

import dotenv

from src.media_lens.common import LOGGER_NAME
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

    def __init__(self, api_key: str, model: str):
        self.agent: Agent = ClaudeLLMAgent(api_key=api_key, model=model)

    def interpret_from_files(self, files: List[Path]) -> List:
        logger.info(f"Interpreting {len(files)} files")
        content: List[Dict] = []
        for file in files:
            with open(file, "rb") as f:
                article: dict = json.load(f)
                content.append(article)
        return self.interpret(content)

    def interpret(self, content: list) -> List:
        logger.debug(f"Interpreting content: {len(content)} bytes")
        try:
            payload = [
                f"<article>TITLE: {element['title']}\nTEXT: {element['text']}\n</article>\n" for element in content
            ]

            system_message = SYSTEM_PROMPT
            user_message = REASONING_PROMPT.format(
                content=payload
            )

            response: str = self.agent.infer(
                system_prompt=system_message,
                user_prompt=user_message,
            )
            content = json.loads(response)
            return content

        except Exception as e:
            logger.error(f"Error extracting news content: {str(e)}")
            print(traceback.format_exc())
            return []

def main(working_dir: Path, site: str):
    interpreter = LLMWebsiteInterpreter(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model="claude-3-5-sonnet-latest"
    )
    files = [f for f in working_dir.glob(f"{site}-clean-article-*.json")]
    print(json.dumps(interpreter.interpret_from_files(files), indent=2))

if __name__ == '__main__':
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    main(Path("/Users/dan/dev/code/projects/python/media_lens/working/out/2025-02-22T20:49:31+00:00"), "www.bbc.com")