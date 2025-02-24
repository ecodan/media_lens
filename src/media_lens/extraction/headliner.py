import json
import logging
import os
import re
import traceback
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Dict

import dotenv

from src.media_lens.common import LOGGER_NAME, get_project_root
from src.media_lens.extraction.agent import Agent, ClaudeLLMAgent

logger = logging.getLogger(LOGGER_NAME)

SYSTEM_PROMPT: str = """
You are a skilled news content analyzer. Your task is to analyze content from news websites and extract headlines, 
paying special attention to structural hints (such as location, styles and elements) 
 
You only extract factual information.
            
"""

REASONING_PROMPT: str= """

For the following analysis, you will use a Chain of Thought (CoT) approach with reflection.

Your task is {task}.

The data you will use is the following:
<data>
{data}
</data>


Follow these steps:
1. Think through the problem step by step within the <thinking> tags.
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
You will be giving the results of a Chain of Thought (CoT) analysis from another expert agent and will format the top headlines
and their URLs in JSON format.

Here's the previous agent's analysis (note: the final answer is denoted by <output/>):
<analysis>
{analysis}
</analysis>

Now format the headlines returned in the <output/> section as follows:
{{
    "stories": [
        {{
            "title": "<story title exactly as it is on the web page>",
            "date": "<publication date if available>"
            "url": "<link to referenced article>"
        }},
        ...
    ]
}}

Format your response EXACTLY as a JSON object with this structure, and only this structure. Respond ONLY with JSON and no other text.

RESPONSE: 

"""
class Extractor(metaclass=ABCMeta):

    @abstractmethod
    def extract(self, content: str) -> Dict:
        pass

    @staticmethod
    def _truncate_html(html_string, max_tokens=100000):
        """
        Simply truncates HTML content at approximately max_tokens.
        Assumes HTML is already simplified.

        Args:
            html_string (str): Input HTML content
            max_tokens (int): Maximum number of tokens (default 100K)

        Returns:
            str: Truncated HTML string
        """
        # Simple token estimation: split on whitespace and punctuation
        tokens = re.findall(r'\w+|\S', html_string)

        if len(tokens) <= max_tokens:
            return html_string

        # Join the first max_tokens tokens back together
        truncated_tokens = tokens[:max_tokens]
        truncated_text = ''.join(t if not t.isalnum() else ' ' + t for t in truncated_tokens).strip()

        return truncated_text

class LLMExtractor(Extractor):

    def __init__(self, api_key: str, model: str, artifacts_dir: Path):
        super().__init__()
        self.agent: Agent = ClaudeLLMAgent(api_key=api_key, model=model)
        self.artifacts_dir = artifacts_dir

    def extract(self, content: str) -> Dict:
        """
        Use Claude to extract headlines and key stories from HTML content.
        :param content: HTML content
        :return: Dict with headlines and stories
        """
        logger.debug(f"Extracting news content: {len(content)} bytes")
        try:
            # first use CoT to get the best candidates
            prompt: str = REASONING_PROMPT.format(
                task="Indentify the five primary headlines in order of appearance such that they are the most likely headlines that a human viewer would see.",
                data=content,
                rules="""
                * Use judgement to identify the primary headlines. 
                * Often there are smaller supporting stories under a single headlines; use judgement to determine if they are unique enough to be their own headlines.
                * The response MUST have the headlines in order of appearance.
                * The response MUST quote the headlines verbatim.
                * The response MUST include the headline text, the publication date (if available) and the URL to the article.
                * The response SHOULD be in JSON but can also be in markdown.
                """
            )
            resonaing_response: str = self.agent.infer(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
            )

            prompt = GATHERING_PROMPT.format(
                analysis=resonaing_response
            )
            gathering_response: str = self.agent.infer(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt
            )

            # Parse response content as JSON
            content = json.loads(gathering_response)
            return content

        except Exception as e:
            logger.error(f"Error extracting news content: {str(e)}")
            print(traceback.format_exc())
            return {
                "headlines": [],
                "stories": [],
                "error": str(e)
            }

##############################
def main(working_dir: Path):
    extractor: LLMExtractor = LLMExtractor(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model="claude-3-5-sonnet-latest",
        # model="claude-3-5-haiku-latest",
        artifacts_dir=working_dir
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