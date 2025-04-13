import asyncio
import logging
import traceback
from pathlib import Path

import dotenv

from src.media_lens.collection.cleaner import WebpageCleaner, cleaner_for_site
from src.media_lens.collection.scraper import WebpageScraper
from src.media_lens.common import LOGGER_NAME, utc_timestamp, get_project_root, SITES, UTC_REGEX_PATTERN_BW_COMPAT, UTC_DATE_PATTERN_BW_COMPAT, utc_bw_compat_timestamp
from src.media_lens.storage_adapter import StorageAdapter

logger = logging.getLogger(LOGGER_NAME)

class Harvester(object):
    """
    Orchestrates the harvesting of web pages and their cleaning.
    """

    def __init__(self, outdir: Path):
        self.outdir = outdir
        self.storage = StorageAdapter()

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

    async def harvest(self, sites: list[str], browser_type: WebpageScraper.BrowserType = WebpageScraper.BrowserType.MOBILE) -> Path:
        """
        Harvest the sites and save the raw and cleaned content to the outdir.
        :param sites: media sites to harvest
        :param browser_type: DESKTOP or MOBILE
        :return: the newly created artifacts dir
        """
        logger.info(f"Harvesting {len(sites)} sites")
        scraper: WebpageScraper = WebpageScraper()
        
        # Create a timestamped directory
        timestamp = utc_bw_compat_timestamp()
        directory_path = timestamp
        self.storage.create_directory(directory_path)
        
        # For backward compatibility, we'll also create the local directory
        # if we're using local storage
        artifacts_dir: Path = self.outdir / timestamp
        if not self.storage.use_cloud:
            artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        for site in sites:
            try:
                logger.info(f"Harvesting {site}")
                content: str = await scraper.get_page_content(url="https://" + site, browser_type=browser_type)
                
                logger.info(f"Writing {site} to {directory_path}")
                # Use the storage adapter to write content
                file_path = f"{directory_path}/{site}.html"
                self.storage.write_text(file_path, content, encoding="utf-8")
                
                await self._clean_site(directory_path, content, site)
            except Exception as e:
                logger.error(f"Failed to harvest {site}: {e}")
                traceback.print_exc()
        
        return artifacts_dir

    async def _clean_site(self, directory_path, content, site):
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


####################
# TESTING
async def main(sites: list[str], outdir: Path):
    harvester: Harvester = Harvester(outdir=outdir)
    await harvester.harvest(sites=sites)


if __name__ == '__main__':
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    outdir: Path = Path(get_project_root() / "working/out")
    asyncio.run(main(sites=SITES, outdir=outdir))
