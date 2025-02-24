import asyncio
import datetime
import logging
import sys
from logging import Logger
from pathlib import Path

import dotenv

from src.media_lens.collection.cleaner import WebpageCleaner, cleaner_for_site
from src.media_lens.collection.scraper import WebpageScraper
from src.media_lens.common import LOGGER_NAME, utc_timestamp

logger = logging.getLogger(LOGGER_NAME)

class Harvester(object):

    def __init__(self, outdir: Path):
        self.outdir = outdir

    async def re_harvest(self, job_dir: Path, sites: list[str]):
        logger.info(f"Reprocessing {len(sites)} sites in {job_dir.name}")
        for site in sites:
            try:
                with open(job_dir / f"{site}.html", "r") as f:
                    content: str = f.read()
                    await self.clean_site(job_dir, content, site)
            except Exception as e:
                logger.error(f"Failed to re-harvest {site}: {e}")

    async def harvest(self, sites: list[str], browser_type: WebpageScraper.BrowserType = WebpageScraper.BrowserType.MOBILE) -> Path:
        logger.info(f"Harvesting {len(sites)} sites")
        scraper: WebpageScraper = WebpageScraper()
        artifacts_dir: Path = self.outdir / utc_timestamp()
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        for site in sites:
            try:
                logger.info(f"Harvesting {site}")
                content: str = await scraper.get_page_content(url="https://" + site, browser_type=browser_type)
                logger.info(f"Writing {site} to {artifacts_dir}")
                with open(str(artifacts_dir / f"{site}.html"), "w", encoding="utf-8") as f:
                    f.write(content)
                await self.clean_site(artifacts_dir, content, site)
            except Exception as e:
                logger.error(f"Failed to harvest {site}: {e}")
        return artifacts_dir

    async def clean_site(self, artifacts_dir, content, site):
        # clean content
        cleaner: WebpageCleaner = WebpageCleaner(site_cleaner=cleaner_for_site(site))
        clean_content: str = cleaner.clean_html(content)
        clean_content = cleaner.filter_text_elements(clean_content)
        logger.info(f"Writing clean {site} to {artifacts_dir}")
        with open(str(artifacts_dir / f"{site}-clean.html"), "w", encoding="utf-8") as f:
            f.write(clean_content)


####################
async def main(sites: list[str], outdir: Path):
    harvester: Harvester = Harvester(outdir=outdir)
    await harvester.harvest(sites=sites)


if __name__ == '__main__':
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    sites: list[str] = ['www.cnn.com',
                        'www.bbc.com',
                        'www.foxnews.com'
                        ]
    outdir: Path = Path("/Users/dan/dev/code/projects/python/media_lens/working/out")
    asyncio.run(main(sites=sites, outdir=outdir))
