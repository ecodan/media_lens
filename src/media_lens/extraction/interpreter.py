import datetime
import json
import logging
import time
import traceback
from pathlib import Path
from typing import List, Dict

from anthropic import APIError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.media_lens.common import LOGGER_NAME, get_utc_datetime_from_timestamp, get_week_key
from src.media_lens.extraction.agent import Agent, ResponseFormat
from src.media_lens.job_dir import JobDir
from src.media_lens.storage import shared_storage

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

    def __init__(self, agent: Agent, storage=None, last_n_days=None):
        self.agent: Agent = agent
        self.last_n_days = last_n_days  # If set, only use content from the last N days
        self.minimum_calendar_days_required = 7  # Minimum calendar days required for weekly analysis
        self.use_calendar_week_boundaries = False  # Whether to prefer calendar week boundaries
        # Initialize storage adapter if not provided
        if storage is None:
            self.storage = shared_storage
        else:
            self.storage = storage

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=lambda e: isinstance(e, (APIError, APIConnectionError))
    )
    def _call_llm_with_retry(self, user_prompt: str, system_prompt: str, response_format: ResponseFormat = ResponseFormat.TEXT) -> str:
        """Centralized LLM calling with retry logic."""
        return self.agent.invoke(system_prompt=system_prompt, user_prompt=user_prompt, response_format=response_format)

    def _parse_llm_response(self, response: str) -> List[Dict]:
        """
        Parse LLM response.
        Note: Response should already be cleaned if response_format=JSON was used in the agent call.
        """
        try:
            # Sanitize response by removing non-printable characters
            sanitized_response = ''.join(char for char in response if ord(char) >= 32 or char in '\n\r\t')

            if sanitized_response:
                content = json.loads(sanitized_response)
                return content
            else:
                return []

        except json.JSONDecodeError as json_err:
            logger.error(f"JSON parse error: {str(json_err)}")
            return []
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            return []

    def _format_articles_for_llm(self, articles: List[Dict], include_site: bool = False) -> List[str]:
        """Format articles consistently for LLM input."""
        payload = []
        for article in articles:
            if include_site and 'site' in article:
                formatted = f"<article site='{article['site']}'>\nTITLE: {article['title']}\nTEXT: {article['text']}\n</article>\n"
            else:
                formatted = f"<article>TITLE: {article['title']}\nTEXT: {article['text']}\n</article>\n"
            payload.append(formatted)
        return payload

    def interpret_from_files(self, files: List[Path]) -> List:
        """
        Convenience method to create a concatenated list of articles from a list of files.
        :param files: list of files to read and concatenate
        :return:
        """
        logger.info(f"Interpreting {len(files)} files")
        content: List[Dict] = []
        for file in files:
            # Handle either Path objects or string paths
            file_path = str(file) if hasattr(file, 'name') else file
            # Extract only the relative path if it's an absolute path
            if hasattr(file, 'name') and self.storage.local_root in file.parents:
                file_path = str(file.relative_to(self.storage.local_root))

            article: dict = self.storage.read_json(file_path)
            content.append(article)
        return self.interpret_articles(content)

    def interpret_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Core method: analyze pre-loaded article data.
        
        :param articles: List of article dictionaries with 'title' and 'text' keys
        :return: List of question-answer pairs
        """
        return self._interpret_core(articles)

    def interpret_files(self, file_paths: List[str]) -> List[Dict]:
        """
        Convenience method: read files then analyze content.
        
        :param file_paths: List of file paths containing JSON articles
        :return: List of question-answer pairs
        """
        logger.info(f"Interpreting {len(file_paths)} files")
        articles: List[Dict] = []
        for file_path in file_paths:
            # Handle Path objects or string paths
            if hasattr(file_path, 'name'):
                # Path object
                if self.storage.local_root in file_path.parents:
                    storage_path = str(file_path.relative_to(self.storage.local_root))
                else:
                    storage_path = str(file_path)
            else:
                # String path
                storage_path = file_path

            article = self.storage.read_json(storage_path)
            articles.append(article)
        return self.interpret_articles(articles)

    def interpret_jobs(self, job_dirs: List[str], sites: List[str]) -> Dict[str, List[Dict]]:
        """
        Batch processing: analyze multiple jobs/sites.
        
        :param job_dirs: List of job directory paths
        :param sites: List of site names to process
        :return: Dictionary mapping site names to their interpretation results
        """
        results = {}

        for site in sites:
            site_articles = []

            # Gather articles from all job directories for this site
            for job_dir in job_dirs:
                pattern = f"{site}-clean-article-*.json"
                article_files = self.storage.get_files_by_pattern(job_dir, pattern)

                for file_path in sorted(article_files):
                    try:
                        article = self.storage.read_json(file_path)
                        article['site'] = site
                        site_articles.append(article)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to decode JSON from {file_path}")

            if site_articles:
                # Preprocess and analyze
                processed_articles = self._preprocess_articles(site_articles, site_name=site)
                results[site] = self.interpret_articles(processed_articles)
            else:
                logger.warning(f"No articles found for site: {site}")
                results[site] = []

        return results

    def interpret_time_period(self, start_date: datetime.datetime = None, end_date: datetime.datetime = None,
                              sites: List[str] = None, group_by: str = 'week') -> Dict[str, List[Dict]]:
        """
        Time-based analysis with flexible grouping.
        
        :param start_date: Start date for analysis (defaults to current week if None)
        :param end_date: End date for analysis (defaults to current date if None)
        :param sites: List of site names (defaults to all sites if None)
        :param group_by: Grouping method ('week', 'day', or 'all')
        :return: Dictionary mapping time periods to interpretation results
        """
        if sites is None:
            from src.media_lens.common import SITES
            sites = SITES

        if group_by == 'week':
            # Use existing weekly interpretation logic
            if start_date is None and end_date is None:
                # Default to current week only
                weekly_results = self.interpret_weeks(sites, current_week_only=True)
            else:
                # Convert dates to week keys and use specific weeks
                specific_weeks = []
                if start_date:
                    specific_weeks.append(get_week_key(start_date))
                if end_date and end_date != start_date:
                    specific_weeks.append(get_week_key(end_date))

                if specific_weeks:
                    weekly_results = self.interpret_weeks(sites, specific_weeks=list(set(specific_weeks)))
                else:
                    weekly_results = self.interpret_weeks(sites, current_week_only=False)

            # Convert to consistent format
            results = {}
            for result in weekly_results:
                results[result['week']] = result['interpretation']
            return results

        elif group_by == 'day' or group_by == 'all':
            # For daily or all-at-once analysis, gather job directories in date range
            job_dirs = JobDir.list_all(self.storage)

            # Filter by date range if specified
            if start_date or end_date:
                filtered_dirs = []
                for job_dir in job_dirs:
                    if isinstance(job_dir, JobDir):
                        job_date = job_dir.datetime
                    else:
                        try:
                            job_date = get_utc_datetime_from_timestamp(job_dir)
                        except ValueError:
                            continue

                    if start_date and job_date < start_date:
                        continue
                    if end_date and job_date > end_date:
                        continue
                    filtered_dirs.append(job_dir)
                job_dirs = filtered_dirs

            if group_by == 'day':
                # Group by day and analyze each day separately
                day_groups = {}
                for job_dir in job_dirs:
                    if isinstance(job_dir, JobDir):
                        day_key = job_dir.datetime.strftime('%Y-%m-%d')
                        job_path = job_dir.storage_path
                    else:
                        try:
                            job_date = get_utc_datetime_from_timestamp(job_dir)
                            day_key = job_date.strftime('%Y-%m-%d')
                            job_path = job_dir
                        except ValueError:
                            continue

                    if day_key not in day_groups:
                        day_groups[day_key] = []
                    day_groups[day_key].append(job_path)

                # Analyze each day
                results = {}
                for day_key, day_job_dirs in day_groups.items():
                    day_results = self.interpret_jobs(day_job_dirs, sites)
                    # Flatten results for this day
                    day_combined = []
                    for site_results in day_results.values():
                        day_combined.extend(site_results)
                    results[day_key] = day_combined

                return results

            else:  # group_by == 'all'
                # Analyze all together
                job_paths = []
                for job_dir in job_dirs:
                    if isinstance(job_dir, JobDir):
                        job_paths.append(job_dir.storage_path)
                    else:
                        job_paths.append(job_dir)

                all_results = self.interpret_jobs(job_paths, sites)
                # Flatten all results
                combined = []
                for site_results in all_results.values():
                    combined.extend(site_results)

                period_key = f"{start_date.strftime('%Y-%m-%d') if start_date else 'all'}_to_{end_date.strftime('%Y-%m-%d') if end_date else 'now'}"
                return {period_key: combined}

        else:
            raise ValueError(f"Invalid group_by value: {group_by}. Must be 'week', 'day', or 'all'")

    def _interpret_core(self, content: list) -> List:
        """
        Interpret the content of a website using a large language model (LLM).
        :param content: all of the content to interpret
        :return: a list of question and answer pairs
        """
        logger.debug(f"Interpreting content: {len(content)} articles")
        try:
            payload = self._format_articles_for_llm(content)

            response = self._call_llm_with_retry(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=REASONING_PROMPT.format(
                    content=payload
                ),
                response_format=ResponseFormat.JSON
            )

            return self._parse_llm_response(response)

        except Exception as e:
            logger.error(f"Error extracting news content: {str(e)}")
            print(traceback.format_exc())
            return []

    def interpret(self, content: list) -> List:
        """
        Legacy method for backward compatibility - use interpret_articles() instead.
        """
        return self._interpret_core(content)

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

            selected_articles = self._preprocess_articles(site_articles, max_articles_per_site, site)

            # Create payload with site attribution
            payload = self._format_articles_for_llm(selected_articles, include_site=True)

            try:
                logger.info(f"Calling LLM {self.agent.model} for site: {site} with {len(selected_articles)} articles")
                response = self._call_llm_with_retry(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=REASONING_PROMPT.format(
                        content=payload
                    ),
                    response_format=ResponseFormat.JSON
                )

                site_content = self._parse_llm_response(response)

                if site_content:
                    # Ensure questions end with question marks and add site info
                    for qa_pair in site_content:
                        if 'question' in qa_pair:
                            question = qa_pair['question'].rstrip('.!?,:;')
                            qa_pair['question'] = question + '?'
                        qa_pair['site'] = site

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

    def _preprocess_articles(self, articles: List[Dict], max_articles: int = 50, site_name: str = None) -> List[Dict]:
        """Preprocess articles with filtering, truncation, and selection."""
        # Filter out articles with no text content
        filtered_articles = [article for article in articles if article.get('text')]

        if site_name:
            total_words = sum(len(article['text'].split()) for article in filtered_articles)
            logger.debug(f"Total words for {site_name}: {total_words}")

        # Truncate article text to first 5 paragraphs
        for article in filtered_articles:
            paragraphs = article['text'].split('\n\n')
            article['text'] = '\n\n'.join(paragraphs[:5])
            # If no proper paragraphs, limit to first 1000 chars
            if len(paragraphs) <= 1:
                article['text'] = article['text'][:1000]

        if site_name:
            total_words = sum(len(article['text'].split()) for article in filtered_articles)
            logger.debug(f"Total words for {site_name} after truncation: {total_words}")

        # Sort by position if available (prioritizing top headlines)
        sorted_articles = sorted(
            filtered_articles,
            key=lambda x: x.get('position', 999)
        )

        # Take top N articles
        selected_articles = sorted_articles[:max_articles]

        if site_name:
            total_words = sum(len(article['text'].split()) for article in selected_articles)
            logger.debug(f"Total words for {site_name} after selection: {total_words}")

        return selected_articles

    def interpret_weeks(self, sites: list[str],
                        specific_weeks: List[str],
                        use_rolling_for_current: bool = True) -> list[dict]:
        """
        Perform weekly interpretation on content from specified weeks using hybrid approach.

        For the current week (if it's incomplete), uses rolling 7-day analysis or ISO week depending on use_rolling_for_current.
        For historical/completed weeks, uses traditional ISO week boundaries.

        :param sites: List of media sites to interpret
        :param specific_weeks: Interpret these specific weeks (e.g. ["2025-W08", "2025-W09"])
        :param use_rolling_for_current: If True, use rolling 7-day for current week (hybrid mode)
        :return: List of weekly interpretation records
        """

        # Get current week
        current_datetime = datetime.datetime.now(datetime.timezone.utc)
        current_week = get_week_key(current_datetime)
        logger.info(f"Current week is {current_week} (hybrid mode: {use_rolling_for_current})")

        # Group job directories by week using JobDir class
        job_dirs = JobDir.list_all(self.storage)
        weeks = JobDir.group_by_week(job_dirs)

        # Determine which weeks to process
        weeks_to_process = {}
        for week in specific_weeks:
            if week in weeks:
                weeks_to_process[week] = weeks[week]
            else:
                logger.warning(f"Specified week {week} not found in available data")

        logger.info(f"Will process {len(weeks_to_process)} weeks: {', '.join(weeks_to_process.keys())}")

        ret: list[dict] = []
        # Process each selected week
        for week_key, dirs in weeks_to_process.items():
            logger.info(f"Performing weekly interpretation for {week_key}")

            # Determine if this is the current week and should use rolling 7-day analysis
            is_current_week = (week_key == current_week)
            use_rolling = is_current_week and use_rolling_for_current

            intermediate_dir = self.storage.get_intermediate_directory()
            weekly_file_path = f"{intermediate_dir}/weekly-{week_key}-interpreted.json"

            if use_rolling:
                logger.info(f"Using rolling 7-day analysis for current week {week_key}")

                # Use rolling 7-day interpretation
                rolling_result = self.interpret_rolling_7_days(sites=sites, reference_date=current_datetime)

                # Save new rolling interpretation
                try:
                    rolling_interpretation = rolling_result.get("interpretation", [])

                    week_record = {
                        "week": week_key,
                        "file_path": weekly_file_path,
                        "included_days": rolling_result.get("included_days", []),
                        "days_count": rolling_result.get("days_count", 0),
                        "calendar_days_span": rolling_result.get("calendar_days_span", 0),
                        "date_range": rolling_result.get("date_range", ""),
                        "period_type": "rolling_7_days",
                        "interpretation": rolling_interpretation
                    }

                    # Save to storage with metadata
                    interpretation_with_metadata = {
                        "week": week_key,
                        "period_type": "rolling_7_days",
                        "start_date": rolling_result.get("start_date"),
                        "end_date": rolling_result.get("end_date"),
                        "reference_date": rolling_result.get("reference_date"),
                        "included_days": rolling_result.get("included_days", []),
                        "days_count": rolling_result.get("days_count", 0),
                        "calendar_days_span": rolling_result.get("calendar_days_span", 0),
                        "date_range": rolling_result.get("date_range", ""),
                        "generated_at": rolling_result.get("generated_at"),
                        "interpretation": rolling_interpretation
                    }
                    self.storage.write_json(weekly_file_path, interpretation_with_metadata)
                    ret.append(week_record)

                except Exception as e:
                    logger.error(f"Failed to save rolling 7-day interpretation for {week_key}: {str(e)}")
                    fallback = {
                        "week": week_key,
                        "file_path": weekly_file_path,
                        "included_days": rolling_result.get("included_days", []),
                        "days_count": rolling_result.get("days_count", 0),
                        "period_type": "rolling_7_days",
                        "interpretation": [{
                            "question": "Rolling 7-day analysis unavailable",
                            "answer": "The rolling 7-day analysis could not be generated due to technical limitations."
                        }]
                    }
                    ret.append(fallback)
            else:
                # Use traditional ISO week analysis for historical weeks
                logger.info(f"Using traditional ISO week analysis for week {week_key}")

                # aggregate all of the content for the week
                all_content: dict
                included_days: list[str]
                extended_dirs = dirs.copy() if isinstance(dirs, list) else list(dirs)

                all_content, included_days, calendar_days_span, date_range = self._gather_content_with_minimum_days(
                    initial_dirs=extended_dirs,
                    sites=sites,
                    target_week_key=week_key,
                    weeks_data=weeks
                )

                data_days_count = len(included_days)
                logger.info(f"Week {week_key} covers {calendar_days_span} calendar days ({date_range}) with data from {data_days_count} actual days: {', '.join(included_days)}")

                if calendar_days_span < self.minimum_calendar_days_required:
                    logger.warning(f"Week {week_key} only covers {calendar_days_span} calendar days (minimum required: {self.minimum_calendar_days_required})")

                # Skip if no content found
                if sum([len(v) for v in all_content.values()]) == 0:
                    logger.warning(f"No content found for week {week_key}")
                    continue

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

                    # Save weekly interpretation with metadata
                    week_record = {
                        "week": week_key,
                        "file_path": weekly_file_path,
                        "included_days": included_days,
                        "days_count": data_days_count,
                        "calendar_days_span": calendar_days_span,
                        "date_range": date_range,
                        "period_type": "iso_week",
                        "interpretation": weekly_interpretation
                    }

                    # Also save the weekly interpretation to storage with metadata
                    interpretation_with_metadata = {
                        "week": week_key,
                        "period_type": "iso_week",
                        "included_days": included_days,
                        "days_count": data_days_count,
                        "calendar_days_span": calendar_days_span,
                        "date_range": date_range,
                        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "interpretation": weekly_interpretation
                    }
                    self.storage.write_json(weekly_file_path, interpretation_with_metadata)

                    ret.append(week_record)

                except Exception as e:
                    logger.error(f"Failed to complete weekly interpretation for {week_key}: {str(e)}")
                    # Create a fallback interpretation with metadata
                    fallback = {
                        "week": week_key,
                        "file_path": weekly_file_path,
                        "included_days": included_days,
                        "days_count": len(included_days),
                        "period_type": "iso_week",
                        "interpretation": [{
                            "question": "Weekly analysis unavailable",
                            "answer": "The weekly analysis could not be generated due to technical limitations."
                        }]
                    }

                    ret.append(fallback)
        return ret

    def _gather_content(self, dirs, sites) -> tuple[dict, list[str]]:
        # Gather all content from all sites for this week
        all_content: dict = {}
        included_days: list[str] = []

        # If last_n_days is set, calculate the cutoff date
        cutoff_date = None
        if self.last_n_days:
            cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=self.last_n_days)
            logger.info(f"Limiting content to the last {self.last_n_days} days (since {cutoff_date.strftime('%Y-%m-%d')})")

        for site in sites:
            site_content = []
            all_content[site] = site_content

            # Get all articles for this site from all job dirs in this week
            for job_dir in dirs:
                # JobDir objects have a storage_path property for storage operations
                if isinstance(job_dir, JobDir):
                    job_dir_path = job_dir.storage_path
                    job_datetime = job_dir.datetime
                else:
                    # Fallback for legacy string-based directory names
                    job_dir_path = job_dir
                    try:
                        job_datetime = get_utc_datetime_from_timestamp(job_dir)
                    except ValueError:
                        job_datetime = None

                # Check if this job directory is within our date range if cutoff_date is set
                if cutoff_date and job_datetime:
                    if job_datetime < cutoff_date:
                        logger.debug(f"Skipping {job_dir_path} as it's before the cutoff date of {cutoff_date}")
                        continue
                elif cutoff_date and not job_datetime:
                    # If we can't parse the date, include it anyway
                    logger.warning(f"Could not parse date from job dir {job_dir_path}, including anyway")

                # Track which day we're including
                if job_datetime:
                    day_str = job_datetime.strftime('%Y-%m-%d')
                    if day_str not in included_days:
                        included_days.append(day_str)

                # Use storage adapter to find article files
                pattern = f"{site}-clean-article-*.json"
                article_files = self.storage.get_files_by_pattern(job_dir_path, pattern)

                job_content: List = []
                for file_path in sorted(article_files):
                    try:
                        article = self.storage.read_json(file_path)
                        job_content.append(article)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to decode JSON from {file_path}")

                site_content.append(job_content)

        # Sort included days chronologically
        included_days.sort()
        return all_content, included_days

    def _gather_content_with_minimum_days(self, initial_dirs: list, sites: list, target_week_key: str, weeks_data: dict) -> tuple[dict, list[str], int, str]:
        """
        Gather content ensuring minimum calendar days requirement is met.
        If insufficient calendar days coverage, extend backwards to previous weeks until minimum is achieved.
        
        Args:
            initial_dirs: Initial job directories for the target week
            sites: List of sites to collect content from
            target_week_key: The target week (e.g. "2025-W08") 
            weeks_data: All available weeks data for extending
            
        Returns:
            Tuple of (all_content, included_days, calendar_days_span, date_range)
        """
        # Start with the initial directories
        extended_dirs = initial_dirs.copy()

        # Get initial content
        all_content, included_days = self._gather_content(extended_dirs, sites)

        # Calculate calendar days span
        calendar_days_span, date_range = self._calculate_calendar_days_span(included_days)
        data_days_count = len(included_days)

        logger.info(f"Initial content for {target_week_key}: {calendar_days_span} calendar days ({date_range}) with data from {data_days_count} days")

        # If we have enough calendar days coverage or minimum requirement is disabled, return
        if calendar_days_span >= self.minimum_calendar_days_required or self.minimum_calendar_days_required <= 0:
            return all_content, included_days, calendar_days_span, date_range

        # Need to extend backwards to get more calendar days coverage
        logger.info(f"Insufficient calendar days coverage ({calendar_days_span} days). Extending backwards to meet minimum {self.minimum_calendar_days_required} calendar days requirement")

        # Get all week keys sorted in reverse chronological order  
        all_week_keys = sorted(weeks_data.keys(), reverse=True)
        target_week_idx = None

        try:
            target_week_idx = all_week_keys.index(target_week_key)
        except ValueError:
            logger.warning(f"Target week {target_week_key} not found in available data")
            return all_content, included_days, calendar_days_span, date_range

        # Extend backwards one week at a time
        extension_attempts = 0
        max_extension_weeks = 4  # Limit to avoid excessive lookback

        while calendar_days_span < self.minimum_calendar_days_required and extension_attempts < max_extension_weeks:
            # Get the next earlier week
            prev_week_idx = target_week_idx + 1 + extension_attempts

            if prev_week_idx >= len(all_week_keys):
                logger.info(f"No more previous weeks available for extension")
                break

            prev_week_key = all_week_keys[prev_week_idx]
            prev_week_dirs = weeks_data.get(prev_week_key, [])

            if not prev_week_dirs:
                logger.info(f"No job directories found for previous week {prev_week_key}")
                extension_attempts += 1
                continue

            # Add previous week's directories
            for prev_dir in prev_week_dirs:
                if prev_dir not in extended_dirs:
                    extended_dirs.append(prev_dir)

            # Recalculate content with extended directories
            all_content, included_days = self._gather_content(extended_dirs, sites)
            new_calendar_days_span, new_date_range = self._calculate_calendar_days_span(included_days)
            new_data_days_count = len(included_days)

            calendar_days_added = new_calendar_days_span - calendar_days_span
            data_days_added = new_data_days_count - data_days_count
            logger.info(
                f"Extended to include {prev_week_key}: +{calendar_days_added} calendar days, +{data_days_added} data days (total: {new_calendar_days_span} calendar days, {new_data_days_count} data days)")

            calendar_days_span = new_calendar_days_span
            date_range = new_date_range
            data_days_count = new_data_days_count
            extension_attempts += 1

        if calendar_days_span >= self.minimum_calendar_days_required:
            logger.info(f"Successfully extended {target_week_key} to cover {calendar_days_span} calendar days ({date_range}) - minimum {self.minimum_calendar_days_required}")
        else:
            logger.warning(f"Could not meet minimum calendar days requirement for {target_week_key}: got {calendar_days_span} calendar days, needed {self.minimum_calendar_days_required}")

        return all_content, included_days, calendar_days_span, date_range

    def _calculate_calendar_days_span(self, included_days: list[str]) -> tuple[int, str]:
        """
        Calculate the span of calendar days covered by the included days.

        Args:
            included_days: List of date strings in YYYY-MM-DD format

        Returns:
            Tuple of (calendar_days_span, date_range_string)
        """
        if not included_days:
            return 0, ""

        # Sort the days to ensure proper ordering
        sorted_days = sorted(included_days)
        start_date = sorted_days[0]
        end_date = sorted_days[-1]

        # Parse dates
        try:
            start_dt = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError as e:
            logger.warning(f"Could not parse dates for calendar span calculation: {e}")
            return len(included_days), f"{start_date} to {end_date}"

        # Calculate calendar days span (inclusive)
        calendar_days_span = (end_dt - start_dt).days + 1

        if start_date == end_date:
            date_range = start_date
        else:
            date_range = f"{start_date} to {end_date}"

        return calendar_days_span, date_range

    def interpret_rolling_7_days(self, sites: List[str] = None, reference_date: datetime.datetime = None) -> Dict[str, any]:
        """
        Perform rolling 7-day interpretation ending at reference_date.
        This method looks back 7 days from the reference date and analyzes all content found.

        :param sites: List of media sites to interpret (defaults to all sites)
        :param reference_date: End date for the 7-day window (defaults to current date)
        :return: Dictionary with interpretation results and metadata
        """
        if sites is None:
            from src.media_lens.common import SITES
            sites = SITES

        if reference_date is None:
            reference_date = datetime.datetime.now(datetime.timezone.utc)

        # Calculate the 7-day window
        start_date = reference_date - datetime.timedelta(days=6)  # 6 days back + today = 7 days

        logger.info(f"Performing rolling 7-day interpretation from {start_date.strftime('%Y-%m-%d')} to {reference_date.strftime('%Y-%m-%d')}")

        # Get all job directories and filter to the 7-day window
        all_job_dirs = JobDir.list_all(self.storage)
        relevant_job_dirs = []

        for job_dir in all_job_dirs:
            job_date = job_dir.datetime
            # Include jobs that fall within our 7-day window
            if start_date.date() <= job_date.date() <= reference_date.date():
                relevant_job_dirs.append(job_dir)

        if not relevant_job_dirs:
            logger.warning(f"No job directories found in rolling 7-day window {start_date.strftime('%Y-%m-%d')} to {reference_date.strftime('%Y-%m-%d')}")
            return {
                "period_type": "rolling_7_days",
                "start_date": start_date.strftime('%Y-%m-%d'),
                "end_date": reference_date.strftime('%Y-%m-%d'),
                "reference_date": reference_date.strftime('%Y-%m-%d'),
                "included_days": [],
                "days_count": 0,
                "interpretation": []
            }

        logger.info(f"Found {len(relevant_job_dirs)} job directories in rolling 7-day window")

        # Gather content from the relevant job directories
        job_dir_paths = [job_dir.storage_path for job_dir in relevant_job_dirs]
        all_content, included_days = self._gather_content(relevant_job_dirs, sites)

        # Skip if no content found
        if sum([len(v) for v in all_content.values()]) == 0:
            logger.warning(f"No content found in rolling 7-day window")
            return {
                "period_type": "rolling_7_days",
                "start_date": start_date.strftime('%Y-%m-%d'),
                "end_date": reference_date.strftime('%Y-%m-%d'),
                "reference_date": reference_date.strftime('%Y-%m-%d'),
                "included_days": included_days,
                "days_count": len(included_days),
                "interpretation": []
            }

        # Perform interpretation on the aggregated content
        logger.info(f"Analyzing content from {len(included_days)} days: {', '.join(included_days)}")

        rolling_interpretation: List[Dict] = []
        loop_ct: int = 0
        loop_total: int = len(all_content)

        for site, content in all_content.items():
            if content:  # Only process sites with content
                site_interpretation: List[Dict] = self.interpret_site_content(site, content)
                rolling_interpretation.extend(site_interpretation)

                # Pause to avoid LLM throttling (except for last iteration)
                loop_ct += 1
                if loop_ct < loop_total:
                    time.sleep(30)

        # Calculate actual calendar days covered
        calendar_days_span, date_range = self._calculate_calendar_days_span(included_days)

        result = {
            "period_type": "rolling_7_days",
            "start_date": start_date.strftime('%Y-%m-%d'),
            "end_date": reference_date.strftime('%Y-%m-%d'),
            "reference_date": reference_date.strftime('%Y-%m-%d'),
            "included_days": included_days,
            "days_count": len(included_days),
            "calendar_days_span": calendar_days_span,
            "date_range": date_range,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "interpretation": rolling_interpretation
        }

        logger.info(f"Rolling 7-day interpretation completed with {len(rolling_interpretation)} Q&A pairs from {len(included_days)} days")
        return result
