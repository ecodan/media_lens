import logging
import os
from pathlib import Path
from typing import List

import dotenv

from src.media_lens.common import LOGGER_NAME, ANTHROPIC_MODEL, create_logger, get_working_dir
from src.media_lens.extraction.agent import Agent, ClaudeLLMAgent

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

    def generate_summary(self, articles: list[Path]) -> str:
        """
        Generate robust, unbiased summary from the collected articles.
        """
        logger.debug("Starting daily summarization process.")
        # Trim each article to N words (default=500)
        # and remove any non-ASCII characters
        trimmed_articles_list: List[str] = []
        for article in articles:
            with open(article, 'r', encoding='utf-8') as f:
                content: str = f.read()
                trimmed_articles_list.append(' '.join(content.split()[:500]))
        trimmed_articles = 'ARTICLE:\n'.join(trimmed_articles_list)
        # Use the agent to summarize the articles
        summary = self.agent.invoke(system_prompt=SYSTEM_PROMPT, user_prompt=REASONING_PROMPT.format(content=trimmed_articles))

        # extract the <thinking> tags and remove the tags and the content between the tags. Return only the content after the closing </thinking> tag
        # and remove any extraneous whitespace
        summary = summary.split("</thinking>")[-1].strip()
        logger.debug("Daily summarization process complete.")
        return summary

    def generate_summary_from_job_dir(self, job_dir: Path) -> str:
        """
        Generate summary from the job directory.
        :param job_dir: directory containing the articles
        :return: summary of the articles
        """
        logger.info(f"Generating summary from job directory: {job_dir}")
        # Get all the article files in the job directory
        article_files = list(job_dir.glob("*clean-article-*.json"))
        if not article_files:
            logger.warning(f"No article files found in {job_dir}")
        else:
            # Generate summary from the article files
            summary: str = self.generate_summary(article_files)
            with open(job_dir / "daily_news.txt", "w") as f:
                f.write(summary)


def main(job_dir: Path):
    summarizer: DailySummarizer = DailySummarizer(agent=ClaudeLLMAgent(api_key=os.getenv("ANTHROPIC_API_KEY"), model=ANTHROPIC_MODEL))
    summarizer.generate_summary_from_job_dir(job_dir)

if __name__ == "__main__":
    dotenv.load_dotenv()
    create_logger(LOGGER_NAME)
    job_dir: Path = Path(get_working_dir() / "out/2025-03-09_032437")
    if not job_dir.exists():
        raise ValueError(f"Job directory {job_dir} does not exist.")
    main(job_dir)