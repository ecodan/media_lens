import datetime
import hashlib
import json
import logging
import re
import traceback
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict

import dotenv
from anthropic import APIError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.media_lens.common import LOGGER_NAME, get_project_root
from src.media_lens.extraction.agent import Agent, create_agent_from_env, ResponseFormat

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
You are a specialized news content analyzer with expertise in extracting and formatting headlines from web content. Your task is to process the results of a previous Chain of Thought (CoT) 
analysis and format the extracted headlines into a structured JSON format.

Here is the previous agent's Chain of Thought analysis:

<cot_analysis>
{analysis}
</cot_analysis>

Your objective is to extract the headlines from the <output/> section of the above analysis and format them into a specific JSON structure. Follow these steps:

1. Carefully read and analyze the CoT analysis, focusing on the content within the <output/> tags.
2. Extract each headline, along with its associated information (title, date if available, and URL).
3. Format this information into a JSON object following the structure specified below.
4. Ensure that your output is pure JSON, without any additional text, comments, or formatting.

Use the following JSON structure for your output:

{{
    "stories": [
        {{
            "title": "<story title exactly as it is on the web page>",
            "date": "<publication date if available>",
            "url": "<link to referenced article>"
        }},
        ...
    ]
}}

Before providing your final output, show your thinking and verification process inside <analysis/> tags. In this process:
1. Extract and list each headline with its associated information, numbering them sequentially.
2. Verify that each headline has all required information (title, date if available, URL).
3. Double-check the JSON structure by writing out a skeleton of the JSON object.
4. Explicitly confirm that there is no extraneous text or formatting that would interfere with the pure JSON output.

After your analysis process, provide only the formatted JSON as your final output. Do not include any additional text, comments, or formatting outside of the JSON structure.

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
        # Simple token estimation: split on whitespace and punctuation
        tokens = re.findall(r'\w+|\S', html_string)

        if len(tokens) <= max_tokens:
            return html_string

        # Join the first max_tokens tokens back together
        truncated_tokens = tokens[:max_tokens]
        truncated_text = ''.join(t if not t.isalnum() else ' ' + t for t in truncated_tokens).strip()

        return truncated_text


class LLMHeadlineExtractor(HeadlineExtractor):
    """
    Extractor class that uses a large language model (LLM) to extract headlines and key stories from HTML content.
    """

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent: Agent = agent
        self.stats = RetryStats()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=30, max=120),
        retry=lambda e: isinstance(e, (APIError, APIConnectionError))
    )
    def _call_llm(self, user_prompt: str, system_prompt: str, response_format: ResponseFormat = ResponseFormat.TEXT) -> str:
        return self.agent.invoke(system_prompt=system_prompt, user_prompt=user_prompt, response_format=response_format)

    def _update_stats(self, retry_state):
        self.stats.attempts += 1
        self.stats.last_attempt = datetime.datetime.now()
        if retry_state.outcome.failed:
            self.stats.last_error = str(retry_state.outcome.exception())

    @staticmethod
    def _get_content_hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    @lru_cache(maxsize=100)
    def _process_content(self, content_hash: str, content: str) -> Dict:
        """Cache extraction results using content hash as key"""
        logger.debug(f"Processing content with hash: {content_hash} and length: {len(content)} (tokens: {len(content.split())})")
        try:
            # Use existing CoT analysis and gathering process
            reasoning_response = self._call_llm(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=REASONING_PROMPT.format(
                    task="Indentify the five primary headlines in order of appearance such that they are the most likely headlines that a human viewer would see.",
                    data=content,
                    rules="""
                    * Use judgement to identify the primary headlines. 
                    * Often there are smaller supporting stories under a single headlines; use judgement to determine if they are unique enough to be their own headlines.
                    * Some media sites use a "catch phrase" such as "BIG WIN" or "ROLL TIDE"; these are not stand-alone headlines and should be combined with the full text of the actual headline.
                    * The response MUST have the headlines in order of appearance.
                    * The response MUST quote the headlines verbatim. 
                    * The response MUST include the headline text, the publication date (if available) and the URL to the article.
                    * The response SHOULD be in JSON but can also be in markdown.
                    """
                )
            )

            gathering_response = self._call_llm(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=GATHERING_PROMPT.format(analysis=reasoning_response),
                response_format=ResponseFormat.JSON
            )

            return json.loads(gathering_response)

        except Exception as e:
            logger.error(f"Error processing content: {str(e)}")
            return {"error": str(e)}

    def extract(self, content: str) -> Dict:
        """
        Use Claude to extract headlines and key stories from HTML content.
        :param content: HTML content
        :return: Dict with headlines and stories
        """
        logger.debug(f"Extracting news content: {len(content)} bytes")
        try:
            content_hash = self._get_content_hash(content)
            res: Dict = self._process_content(content_hash, self._truncate_html(content, max_tokens=25000))
            if "error" in res:
                return {}  # TODO consider more robust error handling
            return res

        except Exception as e:
            logger.error(f"Error extracting news content: {str(e)}")
            print(traceback.format_exc())
            return {
                "headlines": [],
                "stories": [],
                "error": str(e)
            }


##############################
# TEST
def main(working_dir: Path):
    agent = create_agent_from_env()
    extractor: LLMHeadlineExtractor = LLMHeadlineExtractor(
        agent=agent
    )
    for file in working_dir.glob("*-clean.html"):
        with open(file, "r") as f:
            content = f.read()
            results: dict = extractor.extract(content)
            with open(working_dir / f"{file.stem}-extracted.json", "w") as outf:
                outf.write(json.dumps(results))


if __name__ == '__main__':
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    main(working_dir=Path(get_project_root() / "working/out/test"))
