import asyncio
import json
import logging

import trafilatura
from typing import Optional, Dict
from urllib.parse import urlparse

from src.media_lens.collection.scraper import WebpageScraper
from src.media_lens.common import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

class ArticleSummarizer:
    """
    Simple wrapper around trafilatura to extract article content.
    """
    def __init__(self):
        self.scraper: WebpageScraper = WebpageScraper()

    def _validate_url(self, url: str) -> bool:
        """
        Validate if the provided URL is properly formatted.
        :param url: URL to validate.
        :return: True if URL is properly formatted.
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    async def _fetch_content(self, url: str) -> Optional[str]:
        """
        Fetch the raw HTML content from the URL.
        :param url: The URL to fetch
        :return: Optional[str]: The raw HTML content if successful, None otherwise
        """
        return await self.scraper.get_page_content(url, WebpageScraper.BrowserType.MOBILE)

    async def extract_article(self, url: str) -> Dict[str, Optional[str]]:
        """
        Extract article content from the provided URL.
        :param url: The URL to extract content from
        :return: The extracted article content if successful, None otherwise
        """
        if not self._validate_url(url):
            return {
                "title": None,
                "text": None,
                "error": "Invalid URL format"
            }

        html_content = await self._fetch_content(url)
        if not html_content:
            return {
                "title": None,
                "text": None,
                "error": "Failed to fetch content"
            }

        try:
            # Extract the main content
            raw_extract = trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=True,
                include_images=False,
                output_format='json',
                with_metadata=True
            )
            extracted: dict = json.loads(raw_extract)

            if extracted:

                return {
                    "title": extracted.get("title"),
                    "text": extracted.get("text"),
                    "error": None
                }
            else:
                return {
                    "title": None,
                    "text": None,
                    "error": "No content could be extracted"
                }

        except Exception as e:
            return {
                "title": None,
                "text": None,
                "error": f"Extraction error: {str(e)}"
            }


###############################
async def main():
    summarizer = ArticleSummarizer()
    print(await summarizer.extract_article("https://www.cnn.com/2025/02/21/politics/trump-fires-top-us-general-cq-brown/index.html"))

if __name__ == '__main__':
    asyncio.run(main())