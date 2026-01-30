import asyncio
import json
import logging
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
import trafilatura

from src.media_lens.common import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)


class ArticleCollector:
    """
    Simple wrapper around trafilatura to extract article content.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/604.1"
            }
        )

    def _validate_url(self, url: str) -> bool:
        """
        Validate if the provided URL is properly formatted.
        :param url: URL to validate.
        :return: True if URL is properly formatted.
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    async def _fetch_content(self, url: str) -> Optional[str]:
        """
        Fetch the raw HTML content from the URL.
        Tries live URL first, fallbacks to Wayback Machine if it looks like historical data.
        :param url: The URL to fetch
        :return: Optional[str]: The raw HTML content if successful, None otherwise
        """
        # 1. Try Live URL
        try:
            # article scraper - usage of requests is more stable in this environment
            # use a more generic desktop UA as it's often more reliable for live sites
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
            }
            response = self.session.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.warning(f"Live fetch failed for {url}: {e}")

        # 2. Try Wayback Fallback (for historical data)
        # We assume if we are running in the context of this Wayback scrape,
        # we want to try the archive if the live one fails.
        try:
            # Simple way to get a snapshot: https://web.archive.org/web/0/URL (0 = latest/best)
            wayback_url = f"https://web.archive.org/web/20250120000000id_/{url}"
            # Actually, to be safer, we should search for the date, but many articles
            # are archived around the same time.
            logger.info(f"Trying Wayback fallback for {url}")
            response = self.session.get(wayback_url, timeout=30)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.warning(f"Wayback fallback failed for {url}: {e}")

        return None

    async def extract_article(self, url: str) -> Dict[str, Optional[str]]:
        """
        Extract article content from the provided URL.
        :param url: The URL to extract content from
        :return: The extracted article content if successful, None otherwise
        """
        if not self._validate_url(url):
            return {"title": None, "text": None, "error": "Invalid URL format"}

        html_content = await self._fetch_content(url)
        if not html_content:
            return {"title": None, "text": None, "error": "Failed to fetch content"}

        try:
            # Extract the main content
            raw_extract = trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=True,
                include_images=False,
                output_format="json",
                with_metadata=True,
            )
            extracted: dict = json.loads(raw_extract)

            if extracted:
                return {
                    "title": extracted.get("title"),
                    "text": extracted.get("text"),
                    "error": None,
                }
            else:
                return {"title": None, "text": None, "error": "No content could be extracted"}

        except Exception as e:
            return {"title": None, "text": None, "error": f"Extraction error: {e!s}"}


###############################
async def main():
    collector = ArticleCollector()
    print(
        await collector.extract_article(
            "https://www.cnn.com/2025/02/21/politics/trump-fires-top-us-general-cq-brown/index.html"
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
