import argparse
import asyncio
import json
import logging
import os
import re
import time
from enum import Enum
from pathlib import Path
from typing import List

import dotenv

from src.media_lens.collection.harvester import Harvester
from src.media_lens.common import create_logger, LOGGER_NAME, get_project_root, SITES, ANTHROPIC_MODEL, get_datetime_from_timestamp, get_week_key, get_working_dir
from src.media_lens.extraction.agent import Agent, ClaudeLLMAgent
from src.media_lens.extraction.extractor import ContextExtractor
from src.media_lens.extraction.interpreter import LLMWebsiteInterpreter
from src.media_lens.presentation.deployer import upload_file
from src.media_lens.presentation.html_formatter import generate_html_from_path

logger = logging.getLogger(LOGGER_NAME)

UTC_PATTERN: str = r'\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d\+00:00'


class Steps(Enum):
    HARVEST = "harvest"
    REHARVEST = "re-harvest"
    EXTRACT = "extract"
    INTERPRET = "interpret"
    INTERPRET_WEEKLY = "interpret_weekly"
    DEPLOY = "deploy"


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


async def interpret_weekly(job_dirs_root, sites, current_week_only=True, overwrite=False, specific_weeks=None):
    """
    Perform weekly interpretation on content from specified weeks.
    
    :param job_dirs_root: Root directory containing all job directories
    :param sites: List of media sites to interpret
    :param current_week_only: If True, only interpret the current week
    :param overwrite: If True, overwrite existing weekly interpretations
    :param specific_weeks: If provided, only interpret these specific weeks (e.g. ["2025-W08", "2025-W09"])
    """
    agent: Agent = ClaudeLLMAgent(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=ANTHROPIC_MODEL
    )
    interpreter: LLMWebsiteInterpreter = LLMWebsiteInterpreter(agent=agent)

    logger.info(f"Interpreting weekly content with: current_week_only={current_week_only}, overwrite={overwrite}")
    if specific_weeks:
        logger.info(f"Processing specific weeks: {specific_weeks}")
    
    weekly_results: list[dict] = interpreter.interpret_weeks(
        job_dirs_root=job_dirs_root, 
        sites=sites,
        current_week_only=current_week_only,
        overwrite=overwrite,
        specific_weeks=specific_weeks
    )
    
    # Write results to files
    for result in weekly_results:
        logger.info(f"Writing weekly interpretation for {result['week']} to {result['file_path']}")
        with open(result['file_path'], "w") as f:
            f.write(json.dumps(result['interpretation'], indent=2))


async def extract(job_dir):
    agent: Agent = ClaudeLLMAgent(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=ANTHROPIC_MODEL
    )
    extractor: ContextExtractor = ContextExtractor(agent=agent, working_dir=job_dir)
    await extractor.run(delay_between_sites_secs=60)


async def format_and_deploy(jobs_root: Path):
    template_dir_path: Path = Path(get_project_root() / "config/templates")
    template_name: str = "template_01.j2"  # This is ignored in the new implementation
    
    # Generate all HTML files (index and weekly pages)
    index_html: str = generate_html_from_path(jobs_root, SITES, template_dir_path, template_name)
    
    # Get remote path from environment
    remote_path: str = os.getenv("FTP_REMOTE_PATH")
    if not remote_path:
        logger.error("FTP_REMOTE_PATH environment variable not set, skipping deployment")
        return
    
    logger.info(f"Deploying files to {remote_path}")
    
    # Upload the main index page
    index_local: Path = jobs_root / "medialens.html"
    if index_local.exists():
        logger.info(f"Uploading main index file: {index_local}")
        upload_file(index_local, remote_path)
    else:
        logger.warning(f"Main index file not found at {index_local}")
    
    # Find and upload all weekly pages using glob pattern
    weekly_files = list(jobs_root.glob("medialens-*.html"))
    logger.info(f"Found {len(weekly_files)} weekly HTML files")
    
    for weekly_file in weekly_files:
        logger.info(f"Uploading weekly file: {weekly_file}")
        upload_file(weekly_file, remote_path)
    
    # Look for any additional medialens HTML files in subdirectories
    for subdir in jobs_root.iterdir():
        if subdir.is_dir() and subdir.name != "__pycache__":
            # Check for any HTML files in subdirectories 
            for html_file in subdir.glob("medialens*.html"):
                logger.info(f"Uploading additional HTML file from subdirectory: {html_file}")
                upload_file(html_file, remote_path)


async def reprocess_scraped_content(job_dir, out_dir=None):
    logger.debug(f"Reprocessing scraped content for {job_dir.name}")
    harvester: Harvester = Harvester(outdir=out_dir)
    await harvester.re_harvest(job_dir=job_dir, sites=SITES)
    await extract(job_dir)
    # await interpret(job_dir, SITES)


async def reprocess_all_scraped_content(out_dir: Path):
    logger.info(f"Reprocessing scraped content in {out_dir.name} for sites {SITES}")

    for job_dir in out_dir.iterdir():
        if job_dir.is_dir():
            if re.match(UTC_PATTERN, job_dir.name):
                await reprocess_scraped_content(job_dir, out_dir)


async def complete_job(job_dir: Path, steps: list[str]):
    if Steps.HARVEST.value in steps:
        harvester: Harvester = Harvester(outdir=job_dir)
        await harvester.harvest(sites=SITES)

    if Steps.EXTRACT.value in steps:
        await extract(job_dir)

    if Steps.INTERPRET.value in steps:
        await interpret(job_dir, SITES)


async def complete_all_jobs(out_dir: Path, steps: list[str]):
    # First, process individual job directories
    for job_dir in out_dir.iterdir():
        if job_dir.is_dir():
            if re.match(UTC_PATTERN, job_dir.name):
                await complete_job(job_dir, steps)

    # Then handle weekly interpretation if requested
    if Steps.INTERPRET_WEEKLY.value in steps:
        # By default, only process current week and don't overwrite existing files
        await interpret_weekly(out_dir, SITES, current_week_only=True, overwrite=False)

    # Finally, deploy if requested
    if Steps.DEPLOY.value in steps:
        await format_and_deploy(out_dir)


async def run_new_analysis(out_dir: Path):
    # Harvest
    harvester: Harvester = Harvester(outdir=out_dir)
    artifacts_dir = await harvester.harvest(sites=SITES)

    # Extract
    await extract(artifacts_dir)

    # Interpret individual run
    # await interpret(artifacts_dir, SITES)

    # Output
    await format_and_deploy(out_dir)


async def process_weekly_content(out_dir: Path, current_week_only: bool = True, 
                             overwrite: bool = False, specific_weeks: List[str] = None):
    """
    Process weekly content and deploy the results.
    
    :param out_dir: Directory containing the job directories
    :param current_week_only: If True, only process the current week
    :param overwrite: If True, overwrite existing weekly interpretations
    :param specific_weeks: If provided, only process these specific weeks
    """
    # Interpret weekly content
    await interpret_weekly(
        out_dir, 
        SITES, 
        current_week_only=current_week_only, 
        overwrite=overwrite, 
        specific_weeks=specific_weeks
    )

    # Output
    await format_and_deploy(out_dir)


async def run(steps: list[Steps], out_dir: Path, **kwargs):
    if 'job_dir' not in kwargs or kwargs['job_dir'] == "latest":
        # find the latest job dir
        artifacts_dir: Path = Path(max([d for d in out_dir.iterdir() if d.is_dir() and re.match(UTC_PATTERN, d.name)], key=os.path.getctime))
    else:
        artifacts_dir: Path = Path(kwargs['job_dir'])

    if Steps.HARVEST in steps:
        # Harvest
        harvester: Harvester = Harvester(outdir=out_dir)
        # reassign artifacts_dir to new dir
        artifacts_dir = await harvester.harvest(sites=SITES)
    elif Steps.REHARVEST in steps:
        # Re-Harvest
        harvester: Harvester = Harvester(outdir=out_dir)
        await harvester.re_harvest(sites=SITES, job_dir=artifacts_dir)

    if Steps.EXTRACT in steps:
        # Extract
        await extract(artifacts_dir)

    if Steps.INTERPRET in steps:
        # Interpret individual run
        await interpret(artifacts_dir, SITES)

    if Steps.INTERPRET_WEEKLY in steps:
        # Interpret weekly content
        await interpret_weekly(out_dir, SITES, current_week_only=True, overwrite=True)

    if Steps.DEPLOY in steps:
        # Output
        await format_and_deploy(out_dir)


def main():
    parser = argparse.ArgumentParser(description='Media Lens CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Run command
    run_parser = subparsers.add_parser('run', help='Run the media lens pipeline')
    run_parser.add_argument(
        '-s', '--steps',
        nargs='+',
        choices=[step.value for step in Steps],
        required=True,
        help='One or more steps to execute'
    )
    run_parser.add_argument(
        '-j', '--job-dir',
        default='latest',
        help='Job directory to process (default: latest)'
    )
    run_parser.add_argument(
        '-o', '--output-dir',
        type=Path,
        required=True,
        help='Output directory for artifacts'
    )
    args = parser.parse_args()

    if args.command == 'run':
        steps = [Steps(step) for step in args.steps]
        asyncio.run(run(steps=steps, out_dir=args.output_dir, job_dir=args.job_dir))
    else:
        parser.print_help()

if __name__ == '__main__':
    dotenv.load_dotenv()
    create_logger(LOGGER_NAME, get_working_dir() / "runner.log")
    main()