import asyncio
import gc
import logging
import traceback
from pathlib import Path

import dotenv
import psutil

from src.media_lens.collection.cleaning import WebpageCleaner, cleaner_for_site
from src.media_lens.collection.scraper import WebpageScraper
from src.media_lens.common import LOGGER_NAME, SITES, get_project_root
from src.media_lens.storage import shared_storage

logger = logging.getLogger(LOGGER_NAME)


class Harvester:
    """
    Orchestrates the harvesting of web pages and their cleaning.
    """

    def __init__(self):
        self.storage = shared_storage

    async def re_harvest(self, job_dir: Path, sites: list[str]):
        """
        Re-harvest sites from a previous job without re-downloading. This allows the re-use of the content
        already downloaded.
        :param job_dir: folder containing the downloaded content
        :param sites: media sites to re-harvest
        :return:
        """
        logger.info(f"Reprocessing {len(sites)} sites in {job_dir.name}")
        for site in sites:
            try:
                # Use the storage adapter to read content
                content_path = f"{job_dir.name}/{site}.html"
                if self.storage.file_exists(content_path):
                    content: str = self.storage.read_text(content_path)
                    await self._clean_site(job_dir.name, content, site)
                else:
                    logger.warning(f"Content file not found for {site} in {job_dir.name}")
            except Exception as e:
                logger.error(f"Failed to re-harvest {site}: {e}")
                traceback.print_exc()

    async def harvest(
        self,
        sites: list[str],
        browser_type: WebpageScraper.BrowserType = WebpageScraper.BrowserType.MOBILE,
    ) -> str:
        """
        Harvest the sites and save the raw and cleaned content to the outdir.
        Sequential workflow: scrape then clean.
        :param sites: media sites to harvest
        :param browser_type: DESKTOP or MOBILE
        :return: the newly created job directory path (as string)
        """
        logger.info(f"Harvesting {len(sites)} sites (sequential: scrape → clean)")

        # Phase 1: Scrape all sites
        job_dir = await self.scrape_sites(sites=sites, browser_type=browser_type)

        # Phase 2: Clean all scraped content
        await self.clean_sites(job_dir=job_dir, sites=sites)

        return job_dir

    async def scrape_sites(
        self,
        sites: list[str],
        browser_type: WebpageScraper.BrowserType = WebpageScraper.BrowserType.MOBILE,
    ) -> str:
        """
        Scrape sites and save raw content only.
        :param sites: media sites to scrape
        :param browser_type: DESKTOP or MOBILE
        :return: the newly created job directory path (as string)
        """
        logger.info(f"Scraping {len(sites)} sites")
        scraper: WebpageScraper = WebpageScraper()

        # Create a timestamped job directory using new hierarchical structure
        directory_path = self.storage.get_job_directory()
        self.storage.create_directory(directory_path)

        async def scrape_site(site):
            try:
                logger.info(f"Scraping {site}")
                content: str = await scraper.get_page_content(
                    url="https://" + site, browser_type=browser_type
                )

                if content is None:
                    logger.error(f"Failed to get content for {site}, skipping...")
                    return None, site

                logger.info(f"Writing {site} to {directory_path}")
                # Use the storage adapter to write content
                file_path = f"{directory_path}/{site}.html"
                self.storage.write_text(file_path, content, encoding="utf-8")

                return content, site
            except Exception as e:
                logger.error(f"Failed to scrape {site}: {e}")
                traceback.print_exc()
                return None, site

        # Scrape all sites sequentially
        logger.info("Scraping all sites sequentially")
        scrape_results = []
        for site in sites:
            result = await scrape_site(site)
            scrape_results.append(result)

        # Log results
        successful_sites = []
        for result in scrape_results:
            if isinstance(result, Exception):
                logger.error(f"Scraping failed with exception: {result}")
                continue
            content, site = result
            if content is not None:
                successful_sites.append(site)

        logger.info(f"Successfully scraped {len(successful_sites)} out of {len(sites)} sites")
        return directory_path

    async def clean_sites(self, job_dir: str, sites: list[str]) -> None:
        """
        Clean previously scraped content in the specified job directory.
        :param job_dir: the job directory containing scraped content
        :param sites: media sites to clean
        """
        logger.info(f"Cleaning {len(sites)} sites in {job_dir}")

        successful_cleanings = 0
        for site in sites:
            try:
                # Use the storage adapter to read content
                content_path = f"{job_dir}/{site}.html"
                if self.storage.file_exists(content_path):
                    try:
                        # Get process info and memory before cleaning
                        process = psutil.Process()
                        mem_before_mb = process.memory_info().rss / 1024 / 1024

                        content: str = self.storage.read_text(content_path)
                        await self._clean_site(job_dir, content, site)
                        successful_cleanings += 1

                        # Force garbage collection to free memory after each site
                        del content
                        gc.collect()

                        # Measure memory after cleanup
                        mem_after_mb = process.memory_info().rss / 1024 / 1024
                        mem_reclaimed_mb = mem_before_mb - mem_after_mb

                        logger.info(
                            f"Memory for {site}: {mem_before_mb:.1f}MB → {mem_after_mb:.1f}MB (reclaimed: {mem_reclaimed_mb:+.1f}MB)"
                        )
                    except Exception as e:
                        logger.error(f"Failed to clean {site}: {e}")
                        traceback.print_exc()
                else:
                    logger.warning(f"Scraped content file not found for {site} in {job_dir}")
            except Exception as e:
                logger.error(f"Failed to process {site}: {e}")
                traceback.print_exc()

        logger.info(f"Successfully cleaned {successful_cleanings} out of {len(sites)} sites")

    async def _clean_site(self, directory_path: str, content: str, site: str) -> None:
        """
        Clean the content of the site and save it to the directory.
        :param directory_path: the directory path to save the cleaned content
        :param content: the HTML content to clean
        :param site: the site that produced the content
        :return:
        """
        logger.debug(f"Cleaning {site}")
        # clean content
        cleaner: WebpageCleaner = WebpageCleaner(site_cleaner=cleaner_for_site(site))
        clean_content: str = cleaner.clean_html(content)
        clean_content = cleaner.filter_text_elements(clean_content)

        logger.debug(f"Writing clean {site} to {directory_path}")
        # Use the storage adapter to write cleaned content
        clean_file_path = f"{directory_path}/{site}-clean.html"
        self.storage.write_text(clean_file_path, clean_content, encoding="utf-8")

        # Clean up references to allow garbage collection
        del cleaner
        del clean_content


####################
# TESTING
async def main(sites: list[str], outdir: Path):
    harvester: Harvester = Harvester(outdir=outdir)
    await harvester.harvest(sites=sites)


if __name__ == "__main__":
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    outdir: Path = Path(get_project_root() / "working/out")
    asyncio.run(main(sites=SITES, outdir=outdir))
