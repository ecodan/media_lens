import datetime
import json
import logging
import traceback
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import dotenv

from src.media_lens.common import LOGGER_NAME, get_project_root
from src.media_lens.extraction.agent import Agent, ResponseFormat, create_agent_from_env
from src.media_lens.extraction.exceptions import JSONParsingError

logger = logging.getLogger(LOGGER_NAME)

SYSTEM_PROMPT: str = """
You are a skilled news content analyzer. Your task is to analyze content from news websites and extract headlines,
paying special attention to structural hints (such as location, styles and elements)

You only extract factual information.
"""

REASONING_PROMPT: str = """

For the following analysis, you will use a Chain of Thought (CoT) approach with reflection.

Your task is {task}.

The data you will use is the following:
<data>
{data}
</data>


Follow these steps:
1. Think through the problem step by step within the <thinking> </thinking> tags.
2. Reflect on your thinking to check for any errors or improvements within the <reflection> tags.
3. Make any necessary adjustments based on your reflection.
4. Reflect again on your thinking and adjustments and amend anything required to address shortcomings or improve the thoughts.
5. Make any final adjustments based on your second reflection.
4. Provide your final, answer within the <output> tags.

Important: The <thinking> and <reflection> sections are for your internal reasoning process only.
Do not include any part of the final answer in these sections.
The actual response to the query must be entirely contained within the <output> tags.

Use the following format for your response:
<thinking>
 [Your step-by-step reasoning goes here. This is your internal thought process, not the final answer.]
    <reflection>
     [Your reflection on your reasoning, checking for errors or improvements]
    </reflection>
 [Any adjustments to your thinking based on your reflection]
    <reflection_2>
     [Reflect on the adjustments to determine if they address all potential errors and improvements]
    </reflection_2>
[Any adjustments to your thinking based on your reflection, adjustment and reflection_2]
</thinking>
<output>
 [Your final answer to the query. This is the only part that will be shown to the user.]
</output>

# Rules
{rules}

"""

GATHERING_PROMPT: str = """
You are a specialized news content analyzer. Extract the headlines from the <output/> section of the previous analysis and format them as JSON.

Previous analysis:
<cot_analysis>
{analysis}
</cot_analysis>

Return ONLY valid JSON with this exact structure:
{{
    "stories": [
        {{
            "title": "exact headline text from the page",
            "date": "publication date if available",
            "url": "link to the article"
        }}
    ]
}}

Critical requirements:
- Return ONLY the JSON object, nothing else
- No explanations, comments, or text before/after the JSON
- No markdown code fences
- The "stories" key must be at the root level of the JSON object
"""


@dataclass
class RetryStats:
    attempts: int = 0
    last_error: str | None = None
    last_attempt: datetime.datetime | None = None


class HeadlineExtractor(metaclass=ABCMeta):
    @abstractmethod
    def extract(self, content: str) -> Dict:
        pass

    @staticmethod
    def _truncate_html(html_string: str, max_tokens: int = 100000):
        """
        Simply truncates HTML content at approximately max_tokens.
        Assumes HTML is already simplified.
        :param html_string: HTML content
        :param max_tokens: Maximum number of tokens (default 100K)
        :return: Truncated HTML string
        """
        if len(html_string) <= max_tokens * 4:  # rough estimate
            return html_string

        # Better: just slice the string. Simple but keeps structure intact.
        # We might cut mid-tag, but it's safer than injecting spaces everywhere.
        return html_string[: max_tokens * 4]


class LLMHeadlineExtractor(HeadlineExtractor):
    """
    Extractor class that uses a large language model (LLM) to extract headlines and key stories from HTML content.
    """

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent: Agent = agent
        self.stats = RetryStats()

    def _call_llm(
        self,
        user_prompt: str,
        system_prompt: str,
        response_format: ResponseFormat = ResponseFormat.TEXT,
    ) -> str:
        return self.agent.invoke(
            system_prompt=system_prompt, user_prompt=user_prompt, response_format=response_format
        )

    def _update_stats(self, retry_state):
        self.stats.attempts += 1
        self.stats.last_attempt = datetime.datetime.now()
        if retry_state.outcome.failed:
            self.stats.last_error = str(retry_state.outcome.exception())

    def extract(self, content: str) -> Dict:
        """
        Use Claude to extract headlines and key stories from HTML content.
        :param content: HTML content
        :return: Dict with headlines and stories
        """
        logger.debug(f"Extracting news content: {len(content)} bytes")
        try:
            truncated_content = self._truncate_html(content, max_tokens=25000)
            logger.debug(
                f"Processing content with length: {len(truncated_content)} (tokens: {len(truncated_content.split())})"
            )

            # Use CoT analysis and gathering process
            reasoning_response = self._call_llm(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=REASONING_PROMPT.format(
                    task="Indentify the five primary headlines in order of appearance such that they are the most likely headlines that a human viewer would see.",
                    data=truncated_content,
                    rules="""
                    * Use judgement to identify the primary headlines.
                    * Often there are smaller supporting stories under a single headlines; use judgement to determine if they are unique enough to be their own headlines.
                    * Some media sites use a "catch phrase" such as "BIG WIN" or "ROLL TIDE"; these are not stand-alone headlines and should be combined with the full text of the actual headline.
                    * The response MUST have the headlines in order of appearance.
                    * The response MUST quote the headlines verbatim.
                    * The response MUST include the headline text, the publication date (if available) and the URL to the article.
                    * The response SHOULD be in JSON but can also be in markdown.
                    """,
                ),
            )

            gathering_response = self._call_llm(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=GATHERING_PROMPT.format(analysis=reasoning_response),
                response_format=ResponseFormat.JSON,
            )

            try:
                res = json.loads(gathering_response)
                return res
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed: {e!s}")
                logger.error(f"Raw LLM response (first 1000 chars): {gathering_response[:1000]}")
                raise JSONParsingError(gathering_response, str(e)) from e

        except JSONParsingError as e:
            return {"error": str(e)}  # Return error dict with details
        except Exception as e:
            logger.error(f"Error extracting news content: {e!s}")
            print(traceback.format_exc())
            return {"headlines": [], "stories": [], "error": str(e)}


##############################
# TEST
def main(working_dir: Path):
    agent = create_agent_from_env()
    extractor: LLMHeadlineExtractor = LLMHeadlineExtractor(agent=agent)
    for file in working_dir.glob("*-clean.html"):
        with open(file) as f:
            content = f.read()
            results: dict = extractor.extract(content)
            with open(working_dir / f"{file.stem}-extracted.json", "w") as outf:
                outf.write(json.dumps(results))


if __name__ == "__main__":
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    main(working_dir=Path(get_project_root() / "working/out/test"))
