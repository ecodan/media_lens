import datetime
import json
import logging
import os
import re
import time
import traceback
from pathlib import Path
from typing import List, Dict

import dotenv
from anthropic import APIError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.media_lens.common import LOGGER_NAME, get_project_root, ANTHROPIC_MODEL, UTC_REGEX_PATTERN_BW_COMPAT, get_utc_datetime_from_timestamp, get_week_key, SITES, create_logger
from src.media_lens.extraction.agent import Agent, ClaudeLLMAgent

logger = logging.getLogger(LOGGER_NAME)

SYSTEM_PROMPT: str = """
You are a skilled media analyst and sociologist. You'll be given several news articles and then asked questions
about the content of the articles and what might be deduced from them.
"""

REASONING_PROMPT: str = """
You are a highly skilled media analyst and sociologist tasked with analyzing a set of news articles and providing insights on current events. Your analysis will focus on global issues, with particular attention to the situation in the United States and the performance of the U.S. President.

First, carefully read through the following news content:

{content}

After reading the news content, you will answer a series of questions. For each question, wrap your thought process in <thinking> </thinking> tags to break down your reasoning and ensure thorough analysis before providing your final answer. Pay close attention to the specified output format for each question.

Questions to answer:

1. What is the most important news right now?
   Output format: Concise narrative

2. What are the biggest issues in the world right now?
   Output format: Concise narrative

3. For articles referring to the president of the U.S. (Donald Trump), is the president doing a [poor, ok, good, excellent] job based on the portrayal?
   Output format: [Poor, Ok, Good, Excellent] - reasoning: 50 words or less

4. What are three adjectives that best describe the situation in the U.S.?
   Output format: Adjective, Adjective, Adjective

5. What are three adjectives that best describe the job performance and character of the U.S. President?
   Output format: Adjective, Adjective, Adjective

For each question, follow these steps:
1. List relevant quotes from the news content that support your analysis.
2. Consider multiple perspectives and potential interpretations.
3. For questions 4 and 5, brainstorm a list of potential adjectives before selecting the final three.
4. Formulate your answer based on the evidence in the articles.
5. Double-check that your answer adheres to the specified output format.
6. Ensure your reasoning is clear, concise, and well-supported by the information provided.

Your final response should be formatted as a JSON object containing the questions (as written above) and your answers. Use the following structure:

[
  {{
    "question": "<question as written above>",
    "answer": "<your answer, following the format guidelines for each question>"
  }},
  ...
]

Example of the expected JSON structure (with generic content):

[
  {{
    "question": "What is the most important news right now?",
    "answer": "A concise narrative describing the most important current news."
  }},
  {{
    "question": "What are the biggest issues in the world right now?",
    "answer": "A concise narrative outlining the most significant global issues."
  }},
  {{
    "question": "For articles referring to the president of the U.S. (Donald Trump), is the president doing a [poor, ok, good, excellent] job based on the portrayal?",
    "answer": "Ok - A 50-word explanation of why the portrayal suggests good performance."
  }},
  {{
    "question": "What are three adjectives that best describe the situation in the U.S.?",
    "answer": "Adjective1, Adjective2, Adjective3"
  }},
  {{
    "question": "What are three adjectives that best describe the job performance and character of the U.S. President?",
    "answer": "Adjective1, Adjective2, Adjective3"
  }}
]

Remember to provide only the JSON response without any additional text.
"""



OLD_REASONING_PROMPT: str = """
Step back, analyze this news content and answer the following questions concisely:
- What is the most important news right now? [Output format: concise narrative]
- What are biggest issues in the world right now? [Output format: concise narrative]
- For articles referring to the president of the U.S. (Donald Trump), is the president is doing a [poor, ok, good, excellent] job based on the portrayal? [Output format: <[Poor, Ok, Good, Excellent]> - <reasoning: 50 words or less>]
- What are three adjectives that best describe the situation in the U.S.? [Output format: Adjective, Adjective, Adjective]
- What are three adjectives that best describe the job performance and character of the U.S. President? [Output format: Adjective, Adjective, Adjective]

You will format your response as a JSON object containing the question (as written above) and answer (generated).

Format your response EXACTLY as a JSON object with this structure, and only this structure:
[
{{
"question": "<question as written above>",
"answer": "<your answer, as text, written in English and sentence case using the format guidelines for each question above>"
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
        return self.agent.invoke(system_prompt=system_prompt, user_prompt=user_prompt)


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


    def interpret_site_content(self, site: str, content: List[List[Dict]]) -> List[Dict]:
        """
        Interpret a bulk amount of content from a site.
        :param site: The name of the site
        :param content: List of lists of content dicts (title, text) for each day
        :return: List of question and answer pairs analyzing the whole week
        """
        logger.debug(f"Interpreting {len(content)} articles of content from {site}")
        try:
            max_articles_per_site = 50  # Number of articles to process per site
            results = []

            # Flatten and prepare articles from this site
            # Each content_list represents an ordered list of articles from one job
            site_articles = []

            # Collect articles from all content lists for this site
            for day_content in content:
                for article in day_content:
                    site_articles.append({
                        'title': article.get('title', ''),
                        'text': article.get('text', ''),
                        'site': site,
                        'position': day_content.index(article)  # Track position in original list
                    })

            # Skip if no articles for this site
            if not site_articles:
                logger.warning(f"No articles found for site: {site}")
                return results

            selected_articles: list = self._pre_process_articles(max_articles_per_site, site, site_articles)

            # Create payload with site attribution
            payload = [
                f"<article site='{article['site']}'>\nTITLE: {article['title']}\nTEXT: {article['text']}\n</article>\n"
                for article in selected_articles
            ]

            try:
                logger.info(f"Calling LLM {self.agent.model} for site: {site} with {len(selected_articles)} articles")
                response: str = self._call_llm(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=REASONING_PROMPT.format(
                        content=payload
                    )
                )

                # see what's in the response (JSON only or CoT)
                sanitized_response: str = None
                if response.strip().startswith("["):
                    # assume JSON
                    # Fix and sanitize JSON before parsing
                    sanitized_response = ''.join(char for char in response if ord(char) >= 32 or char in '\n\r\t')
                elif "</thinking>" in response:
                    # assume CoT
                    # exclude thought_process
                    trimmed_response: str = re.search(r"</thinking>(.*)", response, re.DOTALL).group(1)
                    # Fix and sanitize JSON before parsing
                    sanitized_response = ''.join(char for char in trimmed_response if ord(char) >= 32 or char in '\n\r\t')
                else:
                    logger.warning(f"Unexpected response format from LLM for site {site}: {response}")

                if sanitized_response:
                    site_content: List = json.loads(sanitized_response)

                    # Ensure the question ends with a question mark
                    for qa_pair in site_content:
                        if 'question' in qa_pair:
                            # Remove trailing punctuation if any
                            question = qa_pair['question'].rstrip('.!?,:;')
                            # Add question mark
                            qa_pair['question'] = question + '?'

                    # Add site information to results and ensure questions end with '?'
                    for item in site_content:
                        item['site'] = site

                    results.extend(site_content)

            except json.JSONDecodeError as json_err:
                logger.error(f"JSON parse error for site {site}: {str(json_err)}")
                results.append({
                    "question": f"Analysis for {site} could not be processed",
                    "answer": f"Due to technical limitations, the analysis for {site} could not be processed.",
                    "site": site
                })
            except Exception as site_err:
                logger.error(f"Error processing site {site}: {str(site_err)}")
                results.append({
                    "question": f"Analysis for {site} not available",
                    "answer": f"The analysis for {site} is currently unavailable due to system limitations.",
                    "site": site
                })
            
            # If no results were gathered, return a fallback response
            if not results:
                return [
                    {
                        "question": "Weekly analysis could not be processed",
                        "answer": "Due to technical limitations, the weekly analysis could not be processed for this site.",
                        "site": site
                    }
                ]
                
            return results

        except Exception as e:
            logger.error(f"Error interpreting weekly content: {str(e)}")
            print(traceback.format_exc())
            # Return a valid fallback structure
            return [
                {
                    "question": "Weekly analysis could not be processed",
                    "answer": "Due to technical errors, the weekly analysis could not be processed for this site.",
                    "site": site
                }
            ]


    @staticmethod
    def _pre_process_articles(max_articles_per_site, site, site_articles) -> List[Dict]:
        # Calculate the total number of words in all articles in site_articles
        total_words: int = sum(len(article['text'].split()) for article in site_articles)
        logger.debug(f"Total words for site {site}: {total_words}")
        # Truncate article text to first 5 paragraphs
        for article in site_articles:
            # Split by paragraphs and keep only first 5
            paragraphs: list[str] = article['text'].split('\n\n')
            article['text'] = '\n\n'.join(paragraphs[:5])
            # If there are no proper paragraphs, limit to first 1000 chars
            if len(paragraphs) <= 1:
                article['text'] = article['text'][:1000]
        # Calculate the total number of words in all articles in site_articles
        total_words = sum(len(article['text'].split()) for article in site_articles)
        logger.debug(f"Total words for site {site} after truncation: {total_words}")
        # Sort articles by position (prioritizing top headlines)
        sorted_site_articles: List[Dict] = sorted(
            site_articles,
            key=lambda x: x.get('position', 999)  # Sort by position, unknown positions last
        )
        # Take top N articles from this site
        selected_articles: List[Dict] = sorted_site_articles[:max_articles_per_site]
        # Calculate the total number of words in all articles in site_articles
        total_words = sum(len(article['text'].split()) for article in selected_articles)
        logger.debug(f"Total words for site {site} after truncation and limiting articles: {total_words}")
        return selected_articles


    def interpret_weeks(self, job_dirs_root: Path, sites: list[str], overwrite: bool = False,
                        current_week_only: bool = True, specific_weeks: List[str] = None) -> list[dict]:
        """
        Perform weekly interpretation on content from specified weeks.
        
        :param job_dirs_root: Path to the root directory containing all job directories
        :param sites: List of media sites to interpret
        :param overwrite: If True, overwrite existing weekly interpretations
        :param current_week_only: If True, only interpret the current week
        :param specific_weeks: If provided, only interpret these specific weeks (e.g. ["2025-W08", "2025-W09"])
        :return: List of weekly interpretation records
        """
        # Get current week
        current_datetime = datetime.datetime.now(datetime.timezone.utc)
        current_week = get_week_key(current_datetime)
        logger.info(f"Current week is {current_week}")
        
        # Group job directories by week
        weeks = {}
        for job_dir in job_dirs_root.iterdir():
            if job_dir.is_dir() and re.match(UTC_REGEX_PATTERN_BW_COMPAT, job_dir.name):
                job_datetime = get_utc_datetime_from_timestamp(job_dir.name)
                week_key = get_week_key(job_datetime)

                if week_key not in weeks:
                    weeks[week_key] = []
                weeks[week_key].append(job_dir)

        # Determine which weeks to process
        weeks_to_process = {}
        if specific_weeks:
            # Process only specified weeks
            for week in specific_weeks:
                if week in weeks:
                    weeks_to_process[week] = weeks[week]
                else:
                    logger.warning(f"Specified week {week} not found in available data")
        elif current_week_only:
            # Process only current week
            if current_week in weeks:
                weeks_to_process[current_week] = weeks[current_week]
            else:
                logger.warning(f"Current week {current_week} not found in available data")
        else:
            # Process all weeks
            weeks_to_process = weeks
        
        logger.info(f"Will process {len(weeks_to_process)} weeks: {', '.join(weeks_to_process.keys())}")

        ret: list[dict] = []
        # Process each selected week
        for week_key, dirs in weeks_to_process.items():
            logger.info(f"Performing weekly interpretation for {week_key}")

            # aggregate all of the content for the week
            all_content: dict = self._gather_content(dirs, sites)

            # Skip if no content found
            if sum([len(v) for v in all_content.values()]) == 0:
                logger.warning(f"No content found for week {week_key}")
                continue

            # Check if weekly interpretation already exists to avoid redoing work
            weekly_file = job_dirs_root / f"weekly-{week_key}-interpreted.json"

            if weekly_file.exists() and not overwrite:
                logger.info(f"Weekly interpretation for {week_key} already exists and overwrite=False")
                
                # Even though we're not overwriting, add the file to results for the return value
                with open(weekly_file, "r") as f:
                    try:
                        existing_interpretation = json.load(f)
                        week_record = {
                            "week": week_key,
                            "file_path": weekly_file,
                            "interpretation": existing_interpretation
                        }
                        ret.append(week_record)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to decode JSON from existing file {weekly_file}")
            else:
                try:
                    # Interpret weekly content
                    weekly_interpretation: List[Dict] = []
                    loop_ct: int = 0
                    loop_total: int = len(all_content)
                    for site, content in all_content.items():
                        site_interpretation: List[Dict] = self.interpret_site_content(site, content)
                        weekly_interpretation.extend(site_interpretation)
                        # pause to avoid LLM throttling
                        loop_ct += 1
                        if loop_ct < loop_total:
                            time.sleep(30)

                    # Save weekly interpretation
                    week_record = {
                        "week": week_key,
                        "file_path": weekly_file,
                        "interpretation": weekly_interpretation
                    }
                    ret.append(week_record)

                except Exception as e:
                    logger.error(f"Failed to complete weekly interpretation for {week_key}: {str(e)}")
                    # Create a fallback interpretation
                    fallback = {
                        "week": week_key,
                        "file_path": weekly_file,
                        "interpretation": {
                            "question": "Weekly analysis unavailable",
                            "answer": "The weekly analysis could not be generated due to technical limitations."
                        }
                    }

                    ret.append(fallback)
        return ret

    @staticmethod
    def _gather_content(dirs, sites) -> dict:
        # Gather all content from all sites for this week
        all_content: dict = {}
        for site in sites:
            site_content = []
            all_content[site] = site_content

            # Get all articles for this site from all job dirs in this week
            for job_dir in dirs:
                article_files = list(job_dir.glob(f"{site}-clean-article-*.json"))
                job_content: List = []
                for file in sorted(article_files):
                    with open(file, "r") as f:
                        try:
                            article = json.load(f)
                            job_content.append(article)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to decode JSON from {file}")
                site_content.append(job_content)

        return all_content


##########################
# TEST
def interpret_single_job(job_dir_root: Path, working_dir_name: str, site: str):
    agent: Agent = ClaudeLLMAgent(api_key=os.getenv("ANTHROPIC_API_KEY"), model=ANTHROPIC_MODEL)
    interpreter = LLMWebsiteInterpreter(agent=agent)

    # process job
    working_dir = job_dir_root / working_dir_name
    files = [f for f in working_dir.glob(f"{site}-clean-article-*.json")]
    print(json.dumps(interpreter.interpret_from_files(files), indent=2))

def interpret_week(job_dirs_root: Path, sites: list[str], overwrite: bool = False, specific_weeks: List[str] = None, current_week_only: bool = True):
    agent: Agent = ClaudeLLMAgent(api_key=os.getenv("ANTHROPIC_API_KEY"), model=ANTHROPIC_MODEL)
    interpreter = LLMWebsiteInterpreter(agent=agent)
    # process week
    content: list[dict] = interpreter.interpret_weeks(job_dirs_root=job_dirs_root, sites=sites, overwrite=overwrite, specific_weeks=specific_weeks, current_week_only=current_week_only)
    for result in content:
        print(json.dumps(result['interpretation'], indent=2))
        with open(result['file_path'], "w") as f:
            f.write(json.dumps(result['interpretation'], indent=2))


if __name__ == '__main__':
    dotenv.load_dotenv()
    create_logger(LOGGER_NAME)
    # interpret_single_job(get_project_root() / "working/out", "2025-03-04T04:35:47+00:00", "www.bbc.com")
    interpret_week(get_project_root() / "working/out", SITES, overwrite=True, current_week_only=True)
    # interpret_week(get_project_root() / "working/out", SITES, overwrite=True, specific_weeks=["2025-W08"])