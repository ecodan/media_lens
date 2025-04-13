import asyncio
import logging
import os
import re
import time
from urllib.parse import urlparse

import dotenv

from src.media_lens.common import LOGGER_NAME, get_project_root, ANTHROPIC_MODEL
from src.media_lens.extraction.agent import ClaudeLLMAgent, Agent
from src.media_lens.extraction.headliner import LLMHeadlineExtractor
from src.media_lens.extraction.collector import ArticleCollector
from src.media_lens.storage_adapter import StorageAdapter

logger = logging.getLogger(LOGGER_NAME)

class ContextExtractor:
    """
    Orchestrates the extraction of headlines and articles from a set of HTML files.
    """
    def __init__(self, agent: Agent, working_dir=None):
        super().__init__()
        self.storage = StorageAdapter()
        self.working_dir = working_dir
        agent: Agent = agent
        self.headline_extractor: LLMHeadlineExtractor = LLMHeadlineExtractor(
            agent=agent
        )
        self.article_collector: ArticleCollector = ArticleCollector()

    @staticmethod
    def _process_relative_url(url: str, filename: str) -> str:
        """
        Process a potentially relative URL, adding https:// and domain if needed.
        :param url: The URL to process
        :param filename: Filename containing the domain (e.g., 'www.cnn.com-extracted.json')
        :returns str: Processed URL with protocol and domain if needed
        :raises ValueError: If domain cannot be extracted from filename
        """
        # Check if URL already has a protocol
        parsed_url = urlparse(url)
        if parsed_url.scheme:
            return url

        # Extract domain from filename
        domain_match = re.match(r'^(www\.[^-]+)', filename)
        if not domain_match:
            raise ValueError('Cannot extract domain from filename')

        domain = domain_match.group(1)

        # Append https:// and domain to the relative URL
        url_path = url[1:] if url.startswith('/') else url
        return f'https://{domain}/{url_path}'

    async def run(self, delay_between_sites_secs: int = 0):
        """
        Run the extraction process.
        Loop through each file in the working directory, extract headlines and articles for the appropriate files, and save results.
        :param delay_between_sites_secs: artificial delay to avoid rate limiting
        :return:
        """
        logger.info(f"Starting extraction at {self.working_dir}")
        
        # Get the directory name (for cloud storage path)
        dir_name = self.working_dir.name
        
        # Get clean HTML files using the storage adapter
        clean_html_files = self.storage.get_files_by_pattern(dir_name, "*-clean.html")
        
        for file_path in clean_html_files:
            logger.info(f"Processing {file_path}")
            
            # Read content using storage adapter
            content = self.storage.read_text(file_path)
            file_name = os.path.basename(file_path)
            file_stem = os.path.splitext(file_name)[0]
            
            try:
                results: dict = self.headline_extractor.extract(content)
                if results.get("error"):
                    logger.warning(f"error in extraction: {results['error']}")
                    continue
                    
                # summarize stories
                for idx, result in enumerate(results.get("stories", [])):
                    url: str = result.get("url")
                    if url is not None:
                        logger.info(f"Scraping article url: {url}")
                        try:
                            article: dict = await self.article_collector.extract_article(self._process_relative_url(url, file_name))
                            if article is not None:
                                # Use storage adapter to write article
                                article_file_path = f"{dir_name}/{file_stem}-article-{idx}.json"
                                result['article_text'] = article_file_path
                                self.storage.write_json(article_file_path, article)
                        except Exception as e:
                            logger.error(f"Failed to extract article: {url} - {str(e)}")
                            
                # Use storage adapter to write extracted data
                extracted_file_path = f"{dir_name}/{file_stem}-extracted.json"
                self.storage.write_json(extracted_file_path, results)
                
            except Exception as e:
                logger.error(f"Failed to extract headlines from {file_path}: {str(e)}")
                
            time.sleep(delay_between_sites_secs)


################
async def main():
    agent: Agent = ClaudeLLMAgent(api_key=os.getenv("ANTHROPIC_API_KEY"), model=ANTHROPIC_MODEL)
    extractor: ContextExtractor = ContextExtractor(
        agent=agent
    )
    await extractor.run()

if __name__ == '__main__':
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())