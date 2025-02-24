import asyncio
import json
import os
import time
from pathlib import Path
import re

import dotenv
from huey import MemoryHuey
from datetime import datetime
import logging

from src.media_lens.collection.harvester import Harvester
from src.media_lens.common import create_logger, LOGGER_NAME
from src.media_lens.extraction.extractor import ContextExtractor
from src.media_lens.extraction.interpreter import LLMWebsiteInterpreter

logger = logging.getLogger(LOGGER_NAME)


async def interpret(job_dir, sites):
    interpreter: LLMWebsiteInterpreter = LLMWebsiteInterpreter(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model="claude-3-5-sonnet-latest"
    )
    for site in sites:
        files = [f for f in job_dir.glob(f"{site}-clean-article-*.json")]
        interpretation: list = interpreter.interpret_from_files(files)
        with open(job_dir / f"{site}-interpreted.json", "w") as file:
            file.write(json.dumps(interpretation, indent=2))
        time.sleep(30)


async def extract(job_dir):
    extractor: ContextExtractor = ContextExtractor(working_dir=job_dir)
    await extractor.run(delay_between_sites_secs=60)


async def reprocess_scraped_content():
    out_dir: Path = Path("/Users/dan/dev/code/projects/python/media_lens/working/out")
    sites: list[str] = ['www.cnn.com',
                        'www.bbc.com',
                        'www.foxnews.com'
                        ]

    logger.info(f"Reprocessing scraped content in {out_dir.name} for sites {sites}")

    utc_pattern = r'\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d\+00:00'
    for job_dir in out_dir.iterdir():
        if job_dir.is_dir():
            if re.match(utc_pattern, job_dir.name):
                logger.debug(f"Reprocessing scraped content for {job_dir.name}")

                harvester: Harvester = Harvester(outdir=out_dir)
                await harvester.re_harvest(job_dir=job_dir, sites=sites)

                await extract(job_dir)

                await interpret(job_dir, sites)


async def run_jobs():

    # Initialize in-memory queue
    huey = MemoryHuey(results=True)  # Keep results in memory

    @huey.task(retries=3, retry_delay=60)  # Retry 3 times, 1 minute between retries
    def scrape_url(url):
        try:
            logger.info(f"Scraping {url} at {datetime.now()}")
            # Your scraping code here
            return {"status": "success", "url": url}
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            raise

    out_dir: Path = Path("/Users/dan/dev/code/projects/python/media_lens/working/out")
    sites: list[str] = ['www.cnn.com',
                        'www.bbc.com',
                        'www.foxnews.com'
                        ]

    # Harvest
    harvester: Harvester = Harvester(outdir=out_dir)
    artifacts_dir = await harvester.harvest(sites=sites)

    # Extract
    await extract(artifacts_dir)

    # Interpret
    await interpret(artifacts_dir, sites)

    # # Usage examples:
    # # Immediate execution
    # result = scrape_url('https://example.com')
    #
    # # Scheduled execution
    # future_result = scrape_url.schedule(
    #     args=('https://example.com',),
    #     delay=60  # Run in 60 seconds
    # )
    #
    # # Check task status
    # print(future_result.get(blocking=True))  # Waits for result

if __name__ == '__main__':
    dotenv.load_dotenv()
    create_logger(LOGGER_NAME)
    asyncio.run(run_jobs())
    # asyncio.run(reprocess_scraped_content())