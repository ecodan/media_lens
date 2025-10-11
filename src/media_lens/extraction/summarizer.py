import logging
from pathlib import Path
from typing import List, Union

import dotenv

from src.media_lens.common import LOGGER_NAME, create_logger
from src.media_lens.extraction.agent import Agent, create_agent_from_env
from src.media_lens.storage import shared_storage
from src.media_lens.storage_adapter import StorageAdapter

logger = logging.getLogger(LOGGER_NAME)

SYSTEM_PROMPT: str = """
You are a skilled media analyst and sociologist. You'll be given several news articles from a range of media services from across the bias spectrum and then given a task to perform on that content.
"""

REASONING_PROMPT: str = """
First, carefully read through the following news content representing 10-15 news articles from a range of media services in 
the order in which they were presented on the news sites. 

The content may be biased, so be sure to read it carefully and consider the context and potential bias of the sources.

{content}

After reading the news content, identify the most important topics and generate an unbias summary of the most important current news.
As you determine which are the most important topics and how to summarize without bias, wrap your thought process in <thinking> </thinking> 
tags to break down your reasoning and ensure thorough analysis before providing your final answer. 
In analyzing the content, follow these steps:

1. Give weight for articles that appear closer to the top of the list or topics that are in multiple articles.
2. Consider multiple perspectives and potential interpretations. Look for bias and don't be influenced by hyperbolic statements.
3. Identify the most important topics and summarize them in a clear and concise manner.
4. Formulate the summary based on the evidence in the articles.
5. Double-check that the summary only contains information from the articles. Do not make up information.
6. Ensure your reasoning is clear, concise, and well-supported by the information provided.

The summary should be clear, concise, and well-supported by the information provided in the articles.
The summary should be 500 words or less.

Here's an example of the output:

<thinking>
1. I read through the articles and identified the most important topics.
2. I noticed that several articles discussed the same topic, which indicates its importance.
3. I considered the potential bias of the sources and made sure to include multiple perspectives.
4. I summarized the most important topics in a clear and concise manner.
... 
</thinking>
There appear to be three primary news stories today.
1. NATO representatives are meeting in Brussels to discuss the ongoing war in Ukraine. With the decrease in support from the US, EU nations have committed EUR100B in weapons and humanitarian aid to Ukraine.
2. The US is facing a potential government shutdown due to disagreements over the budget.  ...


"""


class DailySummarizer:
    """
    DailySummarizer reads a list of article files and
    generates a mashup of the most important news with as
    little bias as possible.
    """

    def __init__(self, agent: Agent):
        self.agent: Agent = agent
        self.storage = shared_storage

    def generate_summary(self, articles: list[Path]) -> str:
        """
        Generate robust, unbiased summary from the collected articles.
        """
        logger.debug("Starting daily summarization process.")
        # Trim each article to N words (default=500)
        # and remove any non-ASCII characters
        trimmed_articles_list: List[str] = []
        for article in articles:
            content: str = self.storage.read_text(article)
            trimmed_articles_list.append(' '.join(content.split()[:500]))
        trimmed_articles = 'ARTICLE:\n'.join(trimmed_articles_list)
        # Use the agent to summarize the articles
        summary = self.agent.invoke(system_prompt=SYSTEM_PROMPT, user_prompt=REASONING_PROMPT.format(content=trimmed_articles))

        # extract the <thinking> tags and remove the tags and the content between the tags. Return only the content after the closing </thinking> tag
        # and remove any extraneous whitespace
        summary = summary.split("</thinking>")[-1].strip()
        logger.debug("Daily summarization process complete.")
        return summary

    def generate_summary_from_job_dir(self, job_dir: Union[Path, str]) -> None:
        """
        Generate summary from the job directory.
        :param job_dir: directory containing the articles (can be Path for local or str for storage adapter)
        :return: summary of the articles
        """
        shared_storage: StorageAdapter = StorageAdapter.get_instance()

        # Convert Path to string if needed for storage adapter
        if isinstance(job_dir, Path):
            job_dir_str = job_dir.name if job_dir.is_absolute() else str(job_dir)
        else:
            job_dir_str = str(job_dir)

        logger.info(f"Generating summary from job directory: {job_dir_str}")

        # Get all the article files using storage adapter
        article_file_paths = shared_storage.get_files_by_pattern(job_dir_str, "*clean-article-*.json")

        if not article_file_paths:
            logger.warning(f"No article files found in {job_dir_str}")
        else:
            # Generate summary from the article files
            summary: str = self.generate_summary(article_file_paths)

            # Write summary using storage adapter
            summary_path = f"{job_dir_str}/daily_news.txt"
            shared_storage.write_text(summary_path, summary)


def main(job_dir: Path):
    agent = create_agent_from_env()
    summarizer: DailySummarizer = DailySummarizer(agent=agent)
    summarizer.generate_summary_from_job_dir(job_dir)


if __name__ == "__main__":
    dotenv.load_dotenv()
    create_logger(LOGGER_NAME)
    from src.media_lens.common import get_working_dir

    jdir: Path = Path(get_working_dir() / "out/2025-03-09_032437")
    if not jdir.exists():
        raise ValueError(f"Job directory {jdir} does not exist.")
    main(jdir)
