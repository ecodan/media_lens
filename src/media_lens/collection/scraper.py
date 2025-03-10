import asyncio
import logging
from enum import Enum
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

from src.media_lens.common import LOGGER_NAME, get_project_root

logger = logging.getLogger(LOGGER_NAME)

class WebpageScraper:

    class BrowserType(Enum):
        DESKTOP = 1
        MOBILE = 2

    @staticmethod
    async def get_page_content(url: str, browser_type: BrowserType ) -> Optional[str]:
        """
        Use Playwright with stealth mode to fetch webpage content.

        :param url: The URL of the news article to scrape
        :param browser_type: MOBILE or DESKTOP
        :return: The page content as string or None if failed
        """
        logger.info(f"Fetching webpage content: {url} with browser type: {browser_type.name}")
        try:
            async with async_playwright() as p:
                # Launch browser in stealth mode
                browser = await p.chromium.launch(headless=True)
                if browser_type == WebpageScraper.BrowserType.DESKTOP:
                    context = await browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    )
                elif browser_type == WebpageScraper.BrowserType.MOBILE:
                    context = await browser.new_context(
                        viewport={'width': 375, 'height': 812},  # iPhone 12 dimensions
                        user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/604.1',
                        device_scale_factor=3,
                        is_mobile=True,
                        has_touch=True
                    )
                else:
                    raise ValueError("Unknown browser type")

                # Enable stealth mode
                page = await context.new_page()
                await stealth_async(page)

                # Additional stealth configurations
                await page.set_extra_http_headers({
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                })

                logger.debug(f"loading page...")
                # Navigate to the page
                await page.goto(url, wait_until='networkidle', timeout=90000)

                # Wait for content to load with a longer timeout
                await page.wait_for_load_state('domcontentloaded', timeout=90000)

                # Get page content
                content = await page.content()

                await browser.close()
                logger.debug(f"finished loading page.")
                return content

        except Exception as e:
            logger.error(f"Error fetching page content: {str(e)}")
            raise e


######################################################
# TEST CODE
async def main(url: str, browser_type: WebpageScraper.BrowserType = WebpageScraper.BrowserType.MOBILE, outfile: Path = None):
    # test code
    scraper = WebpageScraper()
    content = await scraper.get_page_content(url, browser_type)
    if outfile:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(content)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main("http://www.cnn.com", WebpageScraper.BrowserType.MOBILE, outfile=Path(get_project_root() / "working/cnn-mob.html")))
