import asyncio
import json
import os
import time
from pathlib import Path
from typing import List

import dotenv
from huey import MemoryHuey
from datetime import datetime
import logging

from src.media_lens.collection.harvester import Harvester
from src.media_lens.common import create_logger, LOGGER_NAME
from src.media_lens.extraction.extractor import ContextExtractor
from src.media_lens.extraction.interpreter import LLMWebsiteInterpreter

logger = logging.getLogger(LOGGER_NAME)


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
    extractor: ContextExtractor = ContextExtractor(working_dir=artifacts_dir)
    await extractor.run(delay_between_sites_secs=60)

    # Interpret
    interpreter: LLMWebsiteInterpreter = LLMWebsiteInterpreter(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model="claude-3-5-sonnet-latest"
    )
    for site in sites:
        files = [f for f in artifacts_dir.glob(f"{site}-clean-article-*.json")]
        interpretation: list = interpreter.interpret_from_files(files)
        with open(artifacts_dir / f"{site}-interpreted.json", "w") as file:
            file.write(json.dumps(interpretation, indent=2))
        time.sleep(30)

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