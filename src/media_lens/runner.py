import argparse
import asyncio
import datetime
import logging
import os
import re
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import List, Union, Optional

import dotenv
from dateparser.utils.strptime import strptime

from src.media_lens.collection.harvester import Harvester
from src.media_lens.common import create_logger, LOGGER_NAME, get_project_root, SITES, ANTHROPIC_MODEL, get_working_dir, UTC_REGEX_PATTERN_BW_COMPAT, RunState, SITES_DEFAULT
from src.media_lens.extraction.agent import Agent, ClaudeLLMAgent
from src.media_lens.extraction.extractor import ContextExtractor
from src.media_lens.extraction.interpreter import LLMWebsiteInterpreter
from src.media_lens.extraction.summarizer import DailySummarizer
from src.media_lens.presentation.deployer import upload_file
from src.media_lens.presentation.html_formatter import generate_html_from_path
from src.media_lens.storage_adapter import StorageAdapter

logger = logging.getLogger(LOGGER_NAME)
storage = StorageAdapter()


class Steps(Enum):
    HARVEST = "harvest"
    REHARVEST = "re-harvest"
    EXTRACT = "extract"
    INTERPRET = "interpret"
    INTERPRET_WEEKLY = "interpret_weekly"
    SUMMARIZE_DAILY = "summarize_daily"
    FORMAT = "format"
    DEPLOY = "deploy"


async def interpret(job_dir, sites):
    agent: Agent = ClaudeLLMAgent(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=ANTHROPIC_MODEL
    )
    interpreter: LLMWebsiteInterpreter = LLMWebsiteInterpreter(agent=agent)
    for site in sites:
        try:
            # Use storage adapter to get files instead of Path.glob
            file_pattern = f"{site}-clean-article-*.json"
            files = storage.get_files_by_pattern(job_dir, file_pattern)
            
            # Convert to full paths if needed for the interpreter
            file_paths = [storage.get_absolute_path(f) for f in files]
            
            if not files:
                logger.warning(f"No clean article files found for site {site} in {job_dir}")
                # Create an empty interpretation to avoid FileNotFoundError later
                interpretation = [{
                    "question": f"No content available for {site}",
                    "answer": f"No articles were found for {site} in this run."
                }]
            else:
                interpretation: list = interpreter.interpret_from_files(file_paths)
                
            # Ensure we have the directory using storage adapter
            storage.create_directory(job_dir)
            
            # Write the file using storage adapter
            output_path = f"{job_dir}/{site}-interpreted.json"
            storage.write_json(output_path, interpretation)
            
            time.sleep(30)
        except Exception as e:
            logger.error(f"Error interpreting site {site}: {str(e)}")
            # Create a fallback interpretation file
            fallback = [{
                "question": f"Analysis for {site} encountered an error",
                "answer": f"The analysis for {site} could not be completed due to a technical error."
            }]
            output_path = f"{job_dir}/{site}-interpreted.json"
            storage.write_json(output_path, fallback)


async def interpret_weekly(job_dirs_root, sites, current_week_only=True, overwrite=False, specific_weeks=None):
    """
    Perform weekly interpretation on content from specified weeks.
    This will run every Sunday to analyze the last seven days of data.
    
    :param job_dirs_root: Root directory containing all job directories
    :param sites: List of media sites to interpret
    :param current_week_only: If True, only interpret the current week
    :param overwrite: If True, overwrite existing weekly interpretations
    :param specific_weeks: If provided, only interpret these specific weeks (e.g. ["2025-W08", "2025-W09"])
    """
    from src.media_lens.common import is_last_day_of_week, get_week_key
    
    agent: Agent = ClaudeLLMAgent(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=ANTHROPIC_MODEL
    )
    interpreter: LLMWebsiteInterpreter = LLMWebsiteInterpreter(agent=agent)
    
    # Check if today is Sunday (last day of the week) or if specific weeks were provided
    today = datetime.datetime.now(datetime.timezone.utc)
    current_week = get_week_key(today)
    weeks_to_process = specific_weeks or []
    
    # If not Sunday and no specific weeks provided, skip unless force overwrite
    if not is_last_day_of_week(dt=None, tz=None) and not specific_weeks and not overwrite:
        logger.info("Today is not Sunday. Skipping weekly interpretation.")
        return
    
    # If it's Sunday, add current week to process list
    if is_last_day_of_week(dt=None, tz=None) and current_week_only:
        logger.info(f"Today is Sunday. Processing weekly summary with last seven days of data.")
        if current_week not in weeks_to_process:
            weeks_to_process.append(current_week)
    
    # Check if previous week was processed (in case we missed a Sunday)
    previous_week_date = today - datetime.timedelta(days=7)
    previous_week = get_week_key(previous_week_date)
    previous_week_file_path = f"{job_dirs_root}/weekly-{previous_week}-interpreted.json"
    
    # Use storage adapter to check if file exists
    if not storage.file_exists(previous_week_file_path) and not specific_weeks:
        logger.info(f"Previous week {previous_week} was not processed. Adding to processing list.")
        if previous_week not in weeks_to_process:
            weeks_to_process.append(previous_week)
    
    # Only proceed if there are weeks to process
    if weeks_to_process:
        logger.info(f"Processing weeks: {', '.join(weeks_to_process)}")
        
        # Get a timestamp for seven days ago to limit content to last week only
        if is_last_day_of_week(dt=None, tz=None) and not specific_weeks:
            # When running on Sunday with no specific weeks, use last 7 days only
            last_week_date = today - datetime.timedelta(days=7)
            logger.info(f"Limiting content to the last 7 days (since {last_week_date.strftime('%Y-%m-%d')})")
            interpreter.last_n_days = 7
        else:
            # For specific weeks or non-Sunday runs, use default behavior
            interpreter.last_n_days = None
            
        weekly_results: list[dict] = interpreter.interpret_weeks(
            job_dirs_root=job_dirs_root, 
            sites=sites,
            current_week_only=False,  # We're handling this logic ourselves
            overwrite=overwrite,
            specific_weeks=weeks_to_process
        )
        
        # Write results to files using storage adapter
        for result in weekly_results:
            file_path = result['file_path']
            logger.info(f"Writing weekly interpretation for {result['week']} to {file_path}")
            storage.write_json(file_path, result['interpretation'])
    else:
        logger.info("No weeks to process.")




async def extract(job_dir):
    agent: Agent = ClaudeLLMAgent(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=ANTHROPIC_MODEL
    )
    extractor: ContextExtractor = ContextExtractor(agent=agent, working_dir=job_dir)
    await extractor.run(delay_between_sites_secs=60)


async def format_output(jobs_root: Path) -> None:
    """
    Generate all HTML output files from the content in the jobs directory.
    
    Args:
        jobs_root: Root directory containing all job directories
        
    Returns:
        None
    """
    # Get template directory path as string instead of Path object
    template_dir_path: str = str(get_project_root() / "config/templates")
    
    # Generate all HTML files (index and weekly pages)
    index_html: str = generate_html_from_path(jobs_root, SITES, template_dir_path)
    
    logger.info(f"HTML files generated successfully in {jobs_root}")


async def deploy_output(jobs_root: Path) -> None:
    """
    Deploy generated HTML files to the remote server.
    
    Args:
        jobs_root: Root directory containing all job directories and generated HTML files
        
    Returns:
        None
    """
    # Get remote path from environment
    remote_path: str = os.getenv("FTP_REMOTE_PATH")
    if not remote_path:
        logger.error("FTP_REMOTE_PATH environment variable not set, skipping deployment")
        return
    
    logger.info(f"Deploying files to {remote_path}")
    
    # Upload the main index page
    index_local_path = f"{jobs_root}/medialens.html"
    if storage.file_exists(index_local_path):
        logger.info(f"Uploading main index file: {index_local_path}")
        local_temp_path = str(jobs_root / "medialens.html")  # For backward compatibility with upload_file
        # Get content from storage and write to temp file then upload
        index_content = storage.read_text(index_local_path)
        with open(local_temp_path, "w") as f:
            f.write(index_content)
        upload_file(local_temp_path, remote_path)
    else:
        logger.warning(f"Main index file not found at {index_local_path}")
    
    # Find and upload all weekly pages using storage adapter pattern matching
    weekly_files = storage.get_files_by_pattern(jobs_root, "medialens-*.html")
    logger.info(f"Found {len(weekly_files)} weekly HTML files")
    
    for weekly_file in weekly_files:
        logger.info(f"Uploading weekly file: {weekly_file}")
        # Get content and write to temp file then upload
        file_content = storage.read_text(weekly_file)
        local_temp_path = str(jobs_root / os.path.basename(weekly_file))
        with open(local_temp_path, "w") as f:
            f.write(file_content)
        upload_file(local_temp_path, remote_path)
    
    # Get subdirectories using storage.list_files for subdirectories
    all_files = storage.list_files(jobs_root)
    subdirs = set()
    for file in all_files:
        if "/" in file:  # This indicates it's in a subdirectory
            subdir = file.split("/")[0]
            if subdir != "__pycache__":
                subdirs.add(subdir)
    
    # Look for any additional medialens HTML files in subdirectories
    for subdir in subdirs:
        subdir_path = f"{jobs_root}/{subdir}"
        html_files = storage.get_files_by_pattern(subdir_path, "medialens*.html")
        for html_file in html_files:
            logger.info(f"Uploading additional HTML file from subdirectory: {html_file}")
            # Get content and write to temp file then upload
            file_content = storage.read_text(html_file)
            local_temp_path = str(jobs_root / os.path.basename(html_file))
            with open(local_temp_path, "w") as f:
                f.write(file_content)
            upload_file(local_temp_path, remote_path)


async def format_and_deploy(jobs_root: Path) -> None:
    """
    Generate HTML files and deploy them to the remote server.
    This function is kept for backward compatibility.
    
    Args:
        jobs_root: Root directory containing all job directories
        
    Returns:
        None
    """
    await format_output(jobs_root)
    await deploy_output(jobs_root)


async def reprocess_scraped_content(job_dir, out_dir=None):
    # Use string representation instead of Path.name
    job_dir_str = str(job_dir)
    job_dir_name = job_dir_str.split('/')[-1] if '/' in job_dir_str else job_dir_str
    logger.debug(f"Reprocessing scraped content for {job_dir_name}")
    harvester: Harvester = Harvester(outdir=out_dir)
    await harvester.re_harvest(job_dir=job_dir, sites=SITES)
    await extract(job_dir)
    # await interpret(job_dir, SITES)


async def reprocess_all_scraped_content(out_dir: Path):
    logger.info(f"Reprocessing scraped content in {out_dir} for sites {SITES}")

    # Get all directories in out_dir using storage adapter
    all_files = storage.list_files(out_dir)
    job_dirs = set()
    
    # Extract directory names that match UTC pattern
    for file in all_files:
        if "/" in file:
            dir_name = file.split("/")[0]
            if re.match(UTC_REGEX_PATTERN_BW_COMPAT, dir_name):
                job_dirs.add(dir_name)
    
    for job_dir_name in job_dirs:
        job_dir_path = Path(storage.get_absolute_path(f"{out_dir}/{job_dir_name}"))
        await reprocess_scraped_content(job_dir_path, out_dir)


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
    # Get all directories in out_dir using storage adapter
    all_files = storage.list_files(out_dir)
    job_dirs = set()
    
    # Extract directory names that match UTC pattern
    for file in all_files:
        if "/" in file:
            dir_name = file.split("/")[0]
            if re.match(UTC_REGEX_PATTERN_BW_COMPAT, dir_name):
                job_dirs.add(dir_name)
    
    for job_dir_name in job_dirs:
        job_dir_path = Path(storage.get_absolute_path(f"{out_dir}/{job_dir_name}"))
        await complete_job(job_dir_path, steps)

    # Then handle weekly interpretation if requested
    # The modified interpret_weekly will only run on the last day of the week
    # or if a previous week was missed
    if Steps.INTERPRET_WEEKLY.value in steps:
        await interpret_weekly(out_dir, SITES, current_week_only=True, overwrite=False)

    # Format output if requested
    if Steps.FORMAT.value in steps:
        await format_output(out_dir)
        
    # Finally, deploy if requested
    if Steps.DEPLOY.value in steps:
        await deploy_output(out_dir)


async def run_new_analysis(out_dir: Path):
    # Harvest
    harvester: Harvester = Harvester(outdir=out_dir)
    artifacts_dir = await harvester.harvest(sites=SITES)

    # Extract
    await extract(artifacts_dir)

    # Interpret individual run
    # await interpret(artifacts_dir, SITES)

    # Format output
    await format_output(out_dir)
    
    # Deploy output
    await deploy_output(out_dir)


async def process_weekly_content(out_dir: Path, current_week_only: bool = True, 
                             overwrite: bool = False, specific_weeks: List[str] = None):
    """
    Process weekly content and deploy the results.
    This function now respects the last-day-of-week logic in interpret_weekly.
    
    :param out_dir: Directory containing the job directories
    :param current_week_only: If True, only process the current week
    :param overwrite: If True, overwrite existing weekly interpretations
    :param specific_weeks: If provided, only process these specific weeks
    """
    # Interpret weekly content - will only run on last day of week or for missed weeks
    await interpret_weekly(
        out_dir, 
        SITES, 
        current_week_only=current_week_only, 
        overwrite=overwrite, 
        specific_weeks=specific_weeks
    )

    # Format output
    await format_output(out_dir)
    
    # Deploy output
    await deploy_output(out_dir)


async def reinterpret_weeks_from_date(out_dir: Path, start_date: datetime, overwrite: bool = True):
    """
    Reinterpret all weeks from a given start date up to the current week.
    Will only process weeks that fall on Sundays.
    
    :param out_dir: Directory containing the job directories
    :param start_date: The date to start reinterpreting from (will include the week containing this date)
    :param overwrite: If True, overwrite existing weekly interpretations
    """
    from src.media_lens.common import get_week_key
    
    # Make sure start_date has timezone info
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=datetime.timezone.utc)
    
    # Get the current date
    current_date = datetime.datetime.now(datetime.timezone.utc)
    
    # Get week keys for each Sunday from start_date to current date
    weeks_to_process = []
    
    # Start with the week containing the start date
    week_date = start_date
    while week_date <= current_date:
        week_key = get_week_key(week_date)
        if week_key not in weeks_to_process:
            weeks_to_process.append(week_key)
        
        # Move to the next Sunday
        days_until_sunday = (6 - week_date.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7  # If already Sunday, go to next Sunday
        
        week_date = week_date + datetime.timedelta(days=days_until_sunday)
    
    logger.info(f"Reinterpreting {len(weeks_to_process)} weeks: {', '.join(weeks_to_process)}")
    
    # Process all the weeks
    await process_weekly_content(
        out_dir=out_dir,
        current_week_only=False,
        overwrite=overwrite,
        specific_weeks=weeks_to_process
    )

async def summarize_all(out_dir: Path, force: bool = False):
    logger.info(f"Summarizing extracted content in {out_dir}")
    summarizer: DailySummarizer = DailySummarizer(agent=ClaudeLLMAgent(api_key=os.getenv("ANTHROPIC_API_KEY"), model=ANTHROPIC_MODEL))

    # Get all directories in out_dir using storage adapter
    all_files = storage.list_files(out_dir)
    job_dirs = set()
    
    # Extract directory names that match UTC pattern
    for file in all_files:
        # Get the first part of the path which should be the job dir name
        if "/" in file:
            dir_name = file.split("/")[0]
            # Check if it matches the UTC regex pattern
            if re.match(UTC_REGEX_PATTERN_BW_COMPAT, dir_name):
                job_dirs.add(dir_name)
    
    for job_dir_name in job_dirs:
        job_dir = f"{out_dir}/{job_dir_name}"
        # Check if summary file already exists
        summary_file_path = f"{job_dir}/daily_news.txt"
        if storage.file_exists(summary_file_path) and not force:
            logger.info(f"Summary already exists for {job_dir_name}, skipping...")
        else:
            # Convert to Path for compatibility with summarizer
            job_dir_path = Path(storage.get_absolute_path(job_dir))
            summarizer.generate_summary_from_job_dir(job_dir_path)

async def run(steps: list[Steps], out_dir: Path, **kwargs) -> dict:
    """
    Execute the media lens pipeline with the specified steps.
    
    Args:
        steps: List of Steps to execute
        out_dir: Output directory for artifacts
        **kwargs: Additional arguments
        
    Returns:
        dict: Status information about the run
    """
    # Generate a unique run ID and reset the stop flag
    run_id = kwargs.get('run_id', str(uuid.uuid4())[:8])
    RunState.reset(run_id=run_id)
    logger.info(f"Starting run {run_id} with steps: {[step.value for step in steps]}")
    
    result = {
        "run_id": run_id,
        "status": "success",
        "completed_steps": [],
        "error": None
    }
    
    # Make sure the directory exists using storage adapter
    if not storage.file_exists(out_dir):
        # Create directory if it doesn't exist
        storage.create_directory(out_dir)
        logger.info(f"Created output directory {out_dir}")

    if 'job_dir' not in kwargs or kwargs['job_dir'] == "latest":
        # find the latest job dir using storage adapter
        all_files = storage.list_files(out_dir)
        job_dirs = set()
        
        # Extract directory names that match UTC pattern
        for file in all_files:
            if "/" in file:
                dir_name = file.split("/")[0]
                if re.match(UTC_REGEX_PATTERN_BW_COMPAT, dir_name):
                    job_dirs.add(dir_name)
                    
        if job_dirs:
            # Get the latest job dir by sorting and taking the most recent
            artifacts_dir_name = sorted(job_dirs)[-1]  # UTC timestamps sort chronologically
            artifacts_dir = Path(storage.get_absolute_path(f"{out_dir}/{artifacts_dir_name}"))
        else:
            artifacts_dir = None
    else:
        job_dir_path = f"{out_dir}/{kwargs['job_dir']}"
        if not storage.file_exists(job_dir_path):
            raise FileNotFoundError(f"Job directory {job_dir_path} does not exist")
        artifacts_dir = Path(storage.get_absolute_path(job_dir_path))

    try:
        if Steps.HARVEST in steps and not RunState.stop_requested():
            # Harvest
            logger.info(f"[Run {run_id}] Starting harvest step")
            harvester: Harvester = Harvester(outdir=out_dir)
            # reassign artifacts_dir to new dir
            artifacts_dir = await harvester.harvest(sites=SITES)
            result["completed_steps"].append(Steps.HARVEST.value)
            
        elif Steps.REHARVEST in steps and not RunState.stop_requested():
            # Re-Harvest
            logger.info(f"[Run {run_id}] Starting re-harvest step")
            harvester: Harvester = Harvester(outdir=out_dir)
            await harvester.re_harvest(sites=SITES, job_dir=artifacts_dir)
            result["completed_steps"].append(Steps.REHARVEST.value)

        if Steps.EXTRACT in steps and not RunState.stop_requested():
            # Extract
            logger.info(f"[Run {run_id}] Starting extract step")
            await extract(artifacts_dir)
            result["completed_steps"].append(Steps.EXTRACT.value)

        if Steps.INTERPRET in steps and not RunState.stop_requested():
            # Interpret individual run
            logger.info(f"[Run {run_id}] Starting interpret step")
            await interpret(artifacts_dir, SITES)
            result["completed_steps"].append(Steps.INTERPRET.value)

        if Steps.INTERPRET_WEEKLY in steps and not RunState.stop_requested():
            # Interpret weekly content
            logger.info(f"[Run {run_id}] Starting weekly interpretation step")
            await interpret_weekly(out_dir, SITES, current_week_only=True, overwrite=True)
            result["completed_steps"].append(Steps.INTERPRET_WEEKLY.value)

        if Steps.SUMMARIZE_DAILY in steps and not RunState.stop_requested():
            # Summarize daily content
            logger.info(f"[Run {run_id}] Starting daily summarization step")
            summarizer: DailySummarizer = DailySummarizer(agent=ClaudeLLMAgent(api_key=os.getenv("ANTHROPIC_API_KEY"), model=ANTHROPIC_MODEL))
            summarizer.generate_summary_from_job_dir(artifacts_dir)
            result["completed_steps"].append(Steps.SUMMARIZE_DAILY.value)

        if Steps.FORMAT in steps and not RunState.stop_requested():
            # Format output
            logger.info(f"[Run {run_id}] Starting format step")
            await format_output(out_dir)
            result["completed_steps"].append(Steps.FORMAT.value)

        if Steps.DEPLOY in steps and not RunState.stop_requested():
            # Deploy output
            logger.info(f"[Run {run_id}] Starting deployment step")
            await deploy_output(out_dir)
            result["completed_steps"].append(Steps.DEPLOY.value)
            
        if RunState.stop_requested():
            logger.info(f"[Run {run_id}] Run was stopped before completion")
            result["status"] = "stopped"
            
    except Exception as e:
        logger.error(f"[Run {run_id}] Error during execution: {str(e)}", exc_info=True)
        result["status"] = "error"
        result["error"] = str(e)
        
    logger.info(f"[Run {run_id}] Completed with status: {result['status']}")
    return result


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
    run_parser.add_argument(
        '--run-id',
        type=str,
        help='Optional run ID for tracking (auto-generated if not provided)'
    )
    run_parser.add_argument(
        "--sites",
        nargs='+',
        help="List of sites to include"
    )  # Accepts multiple sites


    # Summarize daily news command with option to force resummarization if no summary present
    summarize_parser = subparsers.add_parser('summarize', help='Summarize daily news')
    summarize_parser.add_argument(
        '-o', '--output-dir',
        type=Path,
        required=True,
        help='Output directory for artifacts'
    )
    summarize_parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Force resummarization even if summary exists'
    )
    
    # Weekly reinterpretation command
    reinterpret_parser = subparsers.add_parser('reinterpret-weeks', help='Reinterpret weekly content from a date')
    reinterpret_parser.add_argument(
        '-d', '--date',
        type=str,
        required=True,
        help='Start date in YYYY-MM-DD format'
    )
    reinterpret_parser.add_argument(
        '-o', '--output-dir',
        type=Path,
        required=True,
        help='Output directory for artifacts'
    )
    reinterpret_parser.add_argument(
        '--no-overwrite',
        action='store_true',
        help='Do not overwrite existing weekly interpretations'
    )
    
    # Stop command
    stop_parser = subparsers.add_parser('stop', help='Stop a currently running workflow')

    global SITES

    args = parser.parse_args()
    dotenv.load_dotenv()
    # Use string path for logger
    log_path = str(get_working_dir() / "runner.log")
    create_logger(LOGGER_NAME, log_path)

    if args.command == 'run':
        steps = [Steps(step) for step in args.steps]
        if args.sites:
            SITES = args.sites

        logger.info(f"Using sites: {', '.join(SITES)}")
        run_result = asyncio.run(run(
            steps=steps, 
            out_dir=args.output_dir, 
            job_dir=args.job_dir,
            run_id=args.run_id if hasattr(args, 'run_id') and args.run_id else None
        ))
        if run_result["status"] != "success":
            logger.warning(f"Run completed with status: {run_result['status']}")
            if run_result["status"] == "error":
                logger.error(f"Error: {run_result['error']}")
            if run_result["completed_steps"]:
                logger.info(f"Completed steps: {', '.join(run_result['completed_steps'])}")
        print(f"Run {run_result['run_id']} completed with status: {run_result['status']}")
    elif args.command == 'summarize':
        # Summarize daily news
        # Don't convert to Path, use string directly
        out_dir = args.output_dir
        force = args.force
        if force:
            logger.info("Force resummarization of daily news")
            asyncio.run(summarize_all(out_dir))
        else:
            logger.info("Summarizing daily news without force")
            asyncio.run(summarize_all(out_dir))
    elif args.command == 'reinterpret-weeks':
        # Reinterpret weekly content from a specified date
        try:
            start_date = strptime(args.date, "%Y-%m-%d")
            start_date = start_date.replace(tzinfo=datetime.timezone.utc)
            logger.info(f"Reinterpreting weekly content from {args.date}")
            
            asyncio.run(reinterpret_weeks_from_date(
                out_dir=args.output_dir,
                start_date=start_date,
                overwrite=not args.no_overwrite
            ))
            print(f"Weekly reinterpretation from {args.date} completed successfully")
        except ValueError as e:
            logger.error(f"Invalid date format: {str(e)}")
            print(f"Error: {str(e)}")
    elif args.command == 'stop':
        # Request stop for the current run
        RunState.request_stop()
        logger.info("Stop requested for the current run")
    else:
        parser.print_help()

if __name__ == '__main__':
    main()