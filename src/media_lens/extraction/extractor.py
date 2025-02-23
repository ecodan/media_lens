import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import dotenv

from src.media_lens.common import LOGGER_NAME
from src.media_lens.extraction.headliner import LLMExtractor
from src.media_lens.extraction.summarizer import ArticleSummarizer

logger = logging.getLogger(LOGGER_NAME)

class ContextExtractor:

    def __init__(self, working_dir: Path):
        super().__init__()
        self.working_dir = working_dir
        self.extractor: LLMExtractor = LLMExtractor(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            model="claude-3-5-sonnet-latest",
            # model="claude-3-5-haiku-latest",
            artifacts_dir=working_dir
        )
        self.summarizer: ArticleSummarizer = ArticleSummarizer()

    @staticmethod
    def _process_relative_url(url: str, filename: str) -> str:
        """
        Process a potentially relative URL, adding https:// and domain if needed.

        Args:
            url (str): The URL to process
            filename (str): Filename containing the domain (e.g., 'www.cnn.com-extracted.json')

        Returns:
            str: Processed URL with protocol and domain if needed

        Raises:
            ValueError: If domain cannot be extracted from filename
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
        logger.info(f"Starting extraction at {self.working_dir}")
        # loop through all files to process in this batch
        for file in self.working_dir.glob("*-clean.html"):
            logger.info(f"Processing {file}")
            with open(file, "r") as f:
                content = f.read()
                try:
                    results: dict = self.extractor.extract(content)
                    if results.get("error"):
                        logger.warning(f"error in extraction: {result["error"]}")
                        continue
                    # summarize stories
                    for idx, result in enumerate(results.get("stories", [])):
                        url: str = result.get("url")
                        if url is not None:
                            logger.info(f"Scraping article url: {url}")
                            try:
                                summary: dict = await self.summarizer.extract_article(self._process_relative_url(url, file.name))
                                if summary is not None:
                                    outfile: Path = self.working_dir / f"{file.stem}-article-{idx}.json"
                                    result['article_text'] = str(outfile)
                                    with open(outfile, "w") as aoutf:
                                        aoutf.write(json.dumps(summary))
                            except Exception as e:
                                logger.error(f"Failed to extract article: {url}")
                    with open(self.working_dir / f"{file.stem}-extracted.json", "w") as outf:
                        outf.write(json.dumps(results))
                except Exception as e:
                    logger.error(f"Failed to extract headlines from {file}: {e}")
            time.sleep(delay_between_sites_secs)


################
async def main():
    extractor: ContextExtractor = ContextExtractor(working_dir=Path("/Users/dan/dev/code/projects/python/media_lens/working/out/2025-02-22T20:49:31+00:00"))
    await extractor.run()

if __name__ == '__main__':
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())