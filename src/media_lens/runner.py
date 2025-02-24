import asyncio
import json
import os
import time
from pathlib import Path
import re

import dotenv
import logging

from src.media_lens.collection.harvester import Harvester
from src.media_lens.common import create_logger, LOGGER_NAME, get_project_root, SITES, ANTHROPIC_MODEL
from src.media_lens.extraction.agent import Agent, ClaudeLLMAgent
from src.media_lens.extraction.extractor import ContextExtractor
from src.media_lens.extraction.interpreter import LLMWebsiteInterpreter
from src.media_lens.presentation.deployer import upload_file
from src.media_lens.presentation.html_formatter import generate_html_from_path

logger = logging.getLogger(LOGGER_NAME)



async def interpret(job_dir, sites):
    agent: Agent = ClaudeLLMAgent(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=ANTHROPIC_MODEL
    )
    interpreter: LLMWebsiteInterpreter = LLMWebsiteInterpreter(agent=agent)
    for site in sites:
        files = [f for f in job_dir.glob(f"{site}-clean-article-*.json")]
        interpretation: list = interpreter.interpret_from_files(files)
        with open(job_dir / f"{site}-interpreted.json", "w") as file:
            file.write(json.dumps(interpretation, indent=2))
        time.sleep(30)


async def extract(job_dir):
    agent: Agent = ClaudeLLMAgent(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=ANTHROPIC_MODEL
    )
    extractor: ContextExtractor = ContextExtractor(agent=agent, working_dir=job_dir)
    await extractor.run(delay_between_sites_secs=60)


async def reprocess_scraped_content(out_dir: Path):
    logger.info(f"Reprocessing scraped content in {out_dir.name} for sites {SITES}")

    utc_pattern = r'\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d\+00:00'
    for job_dir in out_dir.iterdir():
        if job_dir.is_dir():
            if re.match(utc_pattern, job_dir.name):
                logger.debug(f"Reprocessing scraped content for {job_dir.name}")

                harvester: Harvester = Harvester(outdir=out_dir)
                await harvester.re_harvest(job_dir=job_dir, sites=SITES)

                await extract(job_dir)

                await interpret(job_dir, SITES)


async def run_new_analysis(out_dir: Path):

    # Harvest
    harvester: Harvester = Harvester(outdir=out_dir)
    artifacts_dir = await harvester.harvest(sites=SITES)

    # Extract
    await extract(artifacts_dir)

    # Interpret
    await interpret(artifacts_dir, SITES)

    # Output
    template_dir_path: Path = Path(get_project_root() / "config/templates")
    template_name: str = "template_01.j2"
    html: str = generate_html_from_path(out_dir, SITES, template_dir_path, template_name)
    with open(out_dir / f"medialens.html", "w") as f:
        f.write(html)

    # Transfer
    local: Path = get_project_root() / "working/out/medialens.html"
    remote: str = os.getenv("FTP_REMOTE_PATH")
    upload_file(local, remote)



if __name__ == '__main__':
    dotenv.load_dotenv()
    create_logger(LOGGER_NAME)
    asyncio.run(run_new_analysis(Path(get_project_root() / "working/out")))
    # asyncio.run(reprocess_scraped_content(Path(get_project_root() / "working/out")))