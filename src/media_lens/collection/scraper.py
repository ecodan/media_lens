import asyncio
import logging
import os
import traceback
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
    async def get_page_content(url: str, browser_type: BrowserType) -> Optional[str]:
        """
        Use Playwright with stealth mode to fetch webpage content.

        :param url: The URL of the news article to scrape
        :param browser_type: MOBILE or DESKTOP
        :return: The page content as string or None if failed
        """
        logger.info(f"Fetching webpage content: {url} with browser type: {browser_type.name}")
        playwright = None
        browser = None
        context = None
        page = None
        content = None

        try:
            playwright = await async_playwright().start()

            # Different browser args based on PLAYWRIGHT_MODE environment variable
            # Defaults to 'cloud' for backwards compatibility and cloud deployment
            playwright_mode = os.getenv('PLAYWRIGHT_MODE', 'cloud').lower()

            if playwright_mode == 'local':
                # Local development arguments (macOS-friendly)
                base_args = [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding'
                ]
                logger.debug("Using local development browser args")
            else:
                # Cloud/container-optimized arguments (default)
                base_args = [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--disable-gpu',
                    '--no-zygote',
                    '--single-process'
                ]
                logger.debug("Using cloud/container-optimized browser args")

            # Launch browser in stealth mode with environment-optimized settings
            browser = await playwright.chromium.launch(
                headless=True,
                timeout=180000,  # 3 minute timeout for browser launch
                args=base_args
            )

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

            try:
                logger.debug("loading page...")
                # Navigate to the page with faster load strategy
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)  # 60 seconds timeout
                logger.debug("page loaded, waiting for additional content...")

                # Wait for dynamic content to load (ads, lazy-loaded content, etc.)
                # await asyncio.sleep(15)
                # logger.debug("getting content...")

                # Get the content if no exceptions occurred
                content = await page.content()
                logger.debug(f"Content retrieved successfully, length: {len(content)}")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout while loading page: {url}; scraping what content is available.")
                try:
                    content = await page.content()
                except Exception as content_error:
                    logger.error(f"Could not get content after timeout: {str(content_error)}")
                    content = None
            except Exception as e:
                logger.warning(f"Error while loading page: {url}; {str(e)}; scraping what content is available.")
                try:
                    content = await page.content()
                except Exception as content_error:
                    logger.error(f"Could not get content after error: {str(content_error)}")
                    content = None

        except Exception as e:
            logger.error(f"Error fetching page content: {str(e)}")
            traceback.print_exc()
            content = None

        finally:
            # Properly close resources in reverse order with timeouts
            logger.debug("Starting resource cleanup...")

            # Give a brief moment for any pending operations to complete
            await asyncio.sleep(0.1)

            if page:
                try:
                    if not page.is_closed():
                        await asyncio.wait_for(page.close(), timeout=5.0)
                except (Exception, asyncio.TimeoutError) as e:
                    if "Target page, context or browser has been closed" not in str(e):
                        logger.warning(f"Error closing page: {str(e)}")

            if context:
                try:
                    await asyncio.wait_for(context.close(), timeout=5.0)
                except (Exception, asyncio.TimeoutError) as e:
                    error_str = str(e)
                    # Suppress expected errors during cleanup
                    if error_str and "Target page, context or browser has been closed" not in error_str:
                        logger.warning(f"Error closing context: {type(e).__name__}: {error_str}")
                    elif not error_str:
                        logger.debug(f"Context close returned empty error: {type(e).__name__}")

            if browser:
                try:
                    if browser.is_connected():
                        await asyncio.wait_for(browser.close(), timeout=10.0)
                except (Exception, asyncio.TimeoutError) as e:
                    error_str = str(e)
                    # Suppress expected errors during cleanup
                    if error_str and "Target page, context or browser has been closed" not in error_str:
                        logger.warning(f"Error closing browser: {type(e).__name__}: {error_str}")
                    elif not error_str:
                        logger.debug(f"Browser close returned empty error: {type(e).__name__}")

            if playwright:
                try:
                    await asyncio.wait_for(playwright.stop(), timeout=10.0)
                except (Exception, asyncio.TimeoutError) as e:
                    logger.warning(f"Error stopping playwright: {str(e)}")

            logger.debug("Resource cleanup completed")

        return content


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
