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

from src.media_lens.common import LOGGER_NAME, get_project_root, ANTHROPIC_MODEL, UTC_PATTERN, get_datetime_from_timestamp, get_week_key, SITES
from src.media_lens.extraction.agent import Agent, ClaudeLLMAgent

logger = logging.getLogger(LOGGER_NAME)

SYSTEM_PROMPT: str = """
You are a skilled media analyst and sociologist. You'll be given several news articles and then asked questions
about the content of the articles and what might be deduced from them.
"""

REASONING_PROMPT: str = """
Step back, analyze this news content and answer the following questions concisely:
- What is the most important news right now? [Output format: concise narrative]
- What are biggest issues in the world right now? [Output format: concise narrative]
- For articles referring to the president of the U.S. (Donald Trump), is the president is doing a [poor, ok, good, excellent] job based on the portrayal? [Output format: Assessment - Reasoning]
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
            
    def interpret_weeks_content(self, all_content: List[Dict]) -> List:
        """
        Interpret a week's worth of content from all sites individually, then aggregate results.
        
        :param all_content: List of dictionaries containing content from all sites for a week
                           [
                           {
                            site: 'www.site.com',
                            content: [ [...article dicts...], [ ... ... ], ... ]
                           },
                           ...]
        :return: List of question and answer pairs analyzing the whole week
        """
        logger.debug(f"Interpreting weekly content from {len(all_content)} sites")
        try:
            max_articles_per_site = 30  # Number of articles to process per site
            all_results = []  # To store results from each site
            
            # Process each site independently
            for site_data in all_content:
                site = site_data.get('site', 'unknown')
                content_lists = site_data.get('content', [])
                
                logger.debug(f"Processing site: {site} with {len(content_lists)} content lists")
                
                # Flatten and prepare articles from this site
                # Each content_list represents an ordered list of articles from one job
                site_articles = []
                
                # Collect articles from all content lists for this site
                for content_list in content_lists:
                    for article in content_list:
                        site_articles.append({
                            'title': article.get('title', ''),
                            'text': article.get('text', ''),
                            'site': site,
                            'position': content_list.index(article)  # Track position in original list
                        })
                
                # Skip if no articles for this site
                if not site_articles:
                    logger.warning(f"No articles found for site: {site}")
                    continue
                # Calculate the total number of words in all articles in site_articles
                total_words = sum(len(article['text'].split()) for article in site_articles)
                logger.debug(f"Total words for site {site}: {total_words}")

                # Truncate article text to first 3 paragraphs
                for article in site_articles:
                    # Split by paragraphs and keep only first 3
                    paragraphs = article['text'].split('\n\n')
                    article['text'] = '\n\n'.join(paragraphs[:5])
                    
                    # If there are no proper paragraphs, limit to first 500 chars
                    if len(paragraphs) <= 1:
                        article['text'] = article['text'][:1000]
                
                # Calculate the total number of words in all articles in site_articles
                total_words = sum(len(article['text'].split()) for article in site_articles)
                logger.debug(f"Total words for site {site} after truncation: {total_words}")

                # Sort articles by position (prioritizing top headlines)
                sorted_site_articles = sorted(
                    site_articles,
                    key=lambda x: x.get('position', 999)  # Sort by position, unknown positions last
                )
                
                # Take top N articles from this site
                selected_articles = sorted_site_articles[:max_articles_per_site]
                
                # Calculate the total number of words in all articles in site_articles
                total_words = sum(len(article['text'].split()) for article in selected_articles)
                logger.debug(f"Total words for site {site} after truncation and limiting articles: {total_words}")

                # Create payload with site attribution
                payload = [
                    f"<article site='{article['site']}'>\nTITLE: {article['title']}\nTEXT: {article['text']}\n</article>\n" 
                    for article in selected_articles
                ]
                
                try:
                    logger.info(f"Calling LLM for site: {site} with {len(selected_articles)} articles")
                    response: str = self._call_llm(
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=REASONING_PROMPT.format(
                            content=payload
                        )
                    )
                    
                    # Fix and sanitize JSON before parsing
                    sanitized_response = ''.join(char for char in response if ord(char) >= 32 or char in '\n\r\t')
                    
                    try:
                        site_content = json.loads(sanitized_response)

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
                            

                        all_results.extend(site_content)
                        
                    except json.JSONDecodeError as json_err:
                        logger.error(f"JSON parse error for site {site}: {str(json_err)}")
                        all_results.append({
                            "question": f"Analysis for {site} could not be processed",
                            "answer": f"Due to technical limitations, the analysis for {site} could not be processed.",
                            "site": site
                        })
                    time.sleep(30)

                except Exception as site_err:
                    logger.error(f"Error processing site {site}: {str(site_err)}")
                    all_results.append({
                        "question": f"Analysis for {site} not available",
                        "answer": f"The analysis for {site} is currently unavailable due to system limitations.",
                        "site": site
                    })
            
            # If no results were gathered, return a fallback response
            if not all_results:
                return [
                    {
                        "question": "Weekly analysis could not be processed",
                        "answer": "Due to technical limitations, the weekly analysis could not be processed. Individual day analyses are still available below."
                    }
                ]
                
            return all_results

        except Exception as e:
            logger.error(f"Error interpreting weekly content: {str(e)}")
            print(traceback.format_exc())
            # Return a valid fallback structure
            return [
                {
                    "question": "Weekly analysis not available",
                    "answer": "The weekly analysis is currently unavailable due to system limitations. Please check individual day analyses below."
                }
            ]


    def interpret_weekly(self, job_dirs_root: Path, sites: list[str], overwrite: bool = False) -> list[dict]:
        # Group job directories by week
        weeks = {}
        for job_dir in job_dirs_root.iterdir():
            if job_dir.is_dir() and re.match(UTC_PATTERN, job_dir.name):
                job_datetime = get_datetime_from_timestamp(job_dir.name)
                week_key = get_week_key(job_datetime)

                if week_key not in weeks:
                    weeks[week_key] = []
                weeks[week_key].append(job_dir)

        ret: list[dict] = []
        # Process each week
        for week_key, dirs in weeks.items():
            logger.info(f"Performing weekly interpretation for {week_key}")

            # Gather all content from all sites for this week
            all_content = []
            for site in sites:
                site_content = []

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

                all_content.append({
                    "site": site,
                    "content": site_content
                })

            # Skip if no content found
            if not all_content:
                logger.warning(f"No content found for week {week_key}")
                continue

            # Check if weekly interpretation already exists to avoid redoing work
            weekly_file = job_dirs_root / f"weekly-{week_key}-interpreted.json"

            if weekly_file.exists() and not overwrite:
                logger.info(f"Weekly interpretation for {week_key} already exists")
            else:
                try:
                    # Interpret weekly content
                    weekly_interpretation = self.interpret_weeks_content(all_content)

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

##########################
# TEST
def interpret_single_job(job_dir_root: Path, working_dir_name: str, site: str):
    agent: Agent = ClaudeLLMAgent(api_key=os.getenv("ANTHROPIC_API_KEY"), model=ANTHROPIC_MODEL)
    interpreter = LLMWebsiteInterpreter(agent=agent)

    # process job
    working_dir = job_dir_root / working_dir_name
    files = [f for f in working_dir.glob(f"{site}-clean-article-*.json")]
    print(json.dumps(interpreter.interpret_from_files(files), indent=2))

def interpret_week(job_dirs_root: Path, sites: list[str], overwrite: bool = False):
    agent: Agent = ClaudeLLMAgent(api_key=os.getenv("ANTHROPIC_API_KEY"), model=ANTHROPIC_MODEL)
    interpreter = LLMWebsiteInterpreter(agent=agent)
    # process week
    content: list[dict] = interpreter.interpret_weekly(job_dirs_root=job_dirs_root, sites=sites, overwrite=overwrite)
    for result in content:
        print(json.dumps(result['interpretation'], indent=2))
        with open(result['file_path'], "w") as f:
            f.write(json.dumps(result['interpretation'], indent=2))


if __name__ == '__main__':
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    # interpret_single_job(get_project_root() / "working/out", "2025-02-27T05:29:00+00:00", "www.bbc.com")
    interpret_week(get_project_root() / "working/out", SITES, overwrite=True)