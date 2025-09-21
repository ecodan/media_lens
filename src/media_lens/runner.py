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
from typing import List

import dotenv
from dateparser.utils.strptime import strptime

from src.media_lens.auditor import audit_days
from src.media_lens.collection.harvester import Harvester
from src.media_lens.common import create_logger, LOGGER_NAME, get_project_root, get_working_dir, UTC_REGEX_PATTERN_BW_COMPAT, RunState, is_last_day_of_week, get_week_key, SITES
from src.media_lens.extraction.agent import Agent, create_agent_from_env
from src.media_lens.extraction.extractor import ContextExtractor
from src.media_lens.extraction.interpreter import LLMWebsiteInterpreter
from src.media_lens.extraction.summarizer import DailySummarizer
from src.media_lens.job_dir import JobDir
from src.media_lens.presentation.deployer import upload_html_content_from_storage, get_deploy_cursor, update_deploy_cursor, get_files_to_deploy, reset_deploy_cursor, rewind_deploy_cursor
from src.media_lens.presentation.html_formatter import generate_html_from_path, reset_format_cursor, rewind_format_cursor
from src.media_lens.storage import shared_storage
from src.media_lens.storage_adapter import StorageAdapter

logger: logging.Logger = logging.getLogger(LOGGER_NAME)
storage: StorageAdapter = shared_storage


class Steps(Enum):
    HARVEST = "harvest"
    HARVEST_SCRAPE = "harvest_scrape"
    HARVEST_CLEAN = "harvest_clean"
    REHARVEST = "re-harvest"
    EXTRACT = "extract"
    INTERPRET = "interpret"
    INTERPRET_WEEKLY = "interpret_weekly"
    SUMMARIZE_DAILY = "summarize_daily"
    FORMAT = "format"
    DEPLOY = "deploy"


async def interpret(job_dir, sites):
    agent: Agent = create_agent_from_env()
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
                interpretation: list = interpreter.interpret_files(file_paths)
                
            # Ensure we have the directory using storage adapter
            storage.create_directory(job_dir)
            
            # Write the interpreted file to intermediate directory organized by job
            # Extract job timestamp from artifacts_dir for organization
            if job_dir.startswith("jobs/"):
                job_timestamp = storage.directory_manager.parse_job_timestamp(job_dir)
            else:
                # Legacy flat directory format
                job_timestamp = job_dir
                
            intermediate_dir = storage.get_intermediate_directory(job_timestamp)
            storage.create_directory(intermediate_dir)
            output_path = f"{intermediate_dir}/{site}-interpreted.json"
            storage.write_json(output_path, interpretation)
            
            time.sleep(30)
        except Exception as e:
            logger.error(f"Error interpreting site {site}: {str(e)}")
            # Create a fallback interpretation file in intermediate directory
            fallback = [{
                "question": f"Analysis for {site} encountered an error",
                "answer": f"The analysis for {site} could not be completed due to a technical error."
            }]
            # Extract job timestamp from artifacts_dir for organization
            if job_dir.startswith("jobs/"):
                job_timestamp = storage.directory_manager.parse_job_timestamp(job_dir)
            else:
                # Legacy flat directory format
                job_timestamp = job_dir
                
            intermediate_dir = storage.get_intermediate_directory(job_timestamp)
            storage.create_directory(intermediate_dir)
            output_path = f"{intermediate_dir}/{site}-interpreted.json"
            storage.write_json(output_path, fallback)


async def interpret_weekly(current_week_only=True, overwrite=False, specific_weeks=None):
    """
    Perform weekly interpretation on content from specified weeks.
    This will run every Sunday to analyze the last seven days of data.
    Ensures that weekly interpretations always include a minimum of 7 days of data.
    
    :param current_week_only: If True, only interpret the current week
    :param overwrite: If True, overwrite existing weekly interpretations
    :param specific_weeks: If provided, only interpret these specific weeks (e.g. ["2025-W08", "2025-W09"])
    """
    
    agent: Agent = create_agent_from_env()
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
        logger.info(f"Today is Sunday. Processing weekly summary with minimum seven days of data.")
        if current_week not in weeks_to_process:
            weeks_to_process.append(current_week)
    
    # Check if previous week was processed (in case we missed a Sunday)
    previous_week_date = today - datetime.timedelta(days=7)
    previous_week = get_week_key(previous_week_date)
    intermediate_dir = storage.get_intermediate_directory()
    previous_week_file_path = f"{intermediate_dir}/weekly-{previous_week}-interpreted.json"
    
    # Use storage adapter to check if file exists
    if not storage.file_exists(previous_week_file_path) and not specific_weeks:
        logger.info(f"Previous week {previous_week} was not processed. Adding to processing list.")
        if previous_week not in weeks_to_process:
            weeks_to_process.append(previous_week)
    
    # Only proceed if there are weeks to process
    if weeks_to_process:
        logger.info(f"Processing weeks: {', '.join(weeks_to_process)}")
        
        # Set minimum calendar days requirement - always ensure at least 7 calendar days are covered
        interpreter.minimum_calendar_days_required = 7
        
        # Configure date range behavior based on run context
        if is_last_day_of_week(dt=None, tz=None) and not specific_weeks:
            # When running on Sunday with no specific weeks, prefer calendar week boundaries
            # but allow extension to meet minimum days requirement
            logger.info(f"Sunday run: Using calendar week boundaries with minimum 7-day requirement")
            interpreter.use_calendar_week_boundaries = True
        else:
            # For specific weeks or non-Sunday runs, use default behavior with minimum requirement
            interpreter.use_calendar_week_boundaries = False
            
        weekly_results: list[dict] = interpreter.interpret_weeks(
            sites=SITES,
            current_week_only=False,  # We're handling this logic ourselves
            overwrite=overwrite,
            specific_weeks=weeks_to_process
        )
        
        # Validate that all results meet minimum calendar days requirement
        for result in weekly_results:
            calendar_days_span = result.get('calendar_days_span', 0)
            data_days_count = result.get('days_count', 0)
            if calendar_days_span < 7:
                logger.warning(f"Weekly interpretation for {result['week']} only covers {calendar_days_span} calendar days (minimum is 7)")
            else:
                logger.info(f"Weekly interpretation for {result['week']} covers {calendar_days_span} calendar days with data from {data_days_count} actual days")
        
        # Write results to files using storage adapter
        for result in weekly_results:
            file_path = result['file_path']
            interpretation_data = {
                'interpretation': result['interpretation'],
                'included_days': result.get('included_days', []),
                'days_count': result.get('days_count', 0),
                'calendar_days_span': result.get('calendar_days_span', 0),
                'date_range': result.get('date_range', ''),
                'week_key': result['week']
            }
            logger.info(f"Writing weekly interpretation for {result['week']} to {file_path}")
            storage.write_json(file_path, interpretation_data)
    else:
        logger.info("No weeks to process.")




async def extract(job_dir):
    agent: Agent = create_agent_from_env()
    extractor: ContextExtractor = ContextExtractor(agent=agent, working_dir=job_dir)
    await extractor.run(delay_between_sites_secs=60)


async def format_output(force_full: bool = False) -> None:
    """
    Generate HTML output files with incremental processing support.
    
    Args:
        force_full: If True, ignore cursor and regenerate everything
        
    Returns:
        None
    """
    # Get template directory path as string instead of Path object
    template_dir_path: str = str(get_project_root() / "config/templates")
    
    # Generate HTML files (index and weekly pages) with cursor support
    generate_html_from_path(SITES, Path(template_dir_path), force_full=force_full)
    
    logger.info("HTML files generated successfully")


async def deploy_output(force_full: bool = False) -> None:
    """
    Deploy generated HTML files to the remote server with incremental processing support.
    
    Args:
        force_full: If True, ignore cursor and deploy all files
        
    Returns:
        None
    """
    logger.info(f"Deploying files (force_full={force_full})")
    
    # Get cursor and determine what files need deployment
    cursor = None if force_full else get_deploy_cursor()
    files_to_deploy = get_files_to_deploy(cursor)
    
    if not files_to_deploy and cursor is not None:
        logger.info("No files need deployment since last deploy - skipping")
        return
    
    # Track deployment success and latest file timestamp
    successful_uploads = []
    latest_file_time = None
    
    # Deploy each file
    for file_path in files_to_deploy:
        logger.info(f"Uploading file: {file_path}")
        success = upload_html_content_from_storage(storage_path=file_path)
        
        if success:
            successful_uploads.append(file_path)
            # Track the latest file modification time for cursor update
            try:
                file_mtime = storage.get_file_modified_time(file_path)
                if file_mtime and (latest_file_time is None or file_mtime > latest_file_time):
                    latest_file_time = file_mtime
            except Exception as e:
                logger.warning(f"Could not get modification time for {file_path}: {e}")
        else:
            logger.error(f"Failed to upload {file_path}")
    
    # Update cursor if we had successful uploads
    if successful_uploads and latest_file_time:
        update_deploy_cursor(latest_file_time)
        logger.info(f"Updated deploy cursor to {latest_file_time.isoformat()}")
    
    logger.info(f"Deployment completed: {len(successful_uploads)}/{len(files_to_deploy)} files uploaded successfully")




async def process_weekly_content(current_week_only: bool = True, 
                       overwrite: bool = False, specific_weeks: List[str] = None):
    """
    Process weekly content and deploy the results.
    This function now respects the last-day-of-week logic in interpret_weekly.
    
    :param current_week_only: If True, only process the current week
    :param overwrite: If True, overwrite existing weekly interpretations
    :param specific_weeks: If provided, only process these specific weeks
    """
    # Interpret weekly content - will only run on last day of week or for missed weeks
    await interpret_weekly(
        current_week_only=current_week_only, 
        overwrite=overwrite, 
        specific_weeks=specific_weeks
    )

    # Format output
    await format_output()
    
    # Deploy output
    await deploy_output()


async def reinterpret_weeks_from_date(start_date: datetime, overwrite: bool = True):
    """
    Reinterpret all weeks from a given start date up to the current week.
    Will only process weeks that fall on Sundays.
    
    :param start_date: The date to start reinterpreting from (will include the week containing this date)
    :param overwrite: If True, overwrite existing weekly interpretations
    """
    
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
        current_week_only=False,
        overwrite=overwrite,
        specific_weeks=weeks_to_process
    )

async def summarize_all(force: bool = False):
    logger.info("Summarizing extracted content")
    summarizer: DailySummarizer = DailySummarizer(agent=create_agent_from_env())

    # Get all directories using storage adapter
    all_dirs = storage.list_directories("")
    job_dirs = set()
    
    # Filter directory names that match UTC pattern
    for dir_name in all_dirs:
        # Check if it matches the UTC regex pattern
        if re.match(UTC_REGEX_PATTERN_BW_COMPAT, dir_name):
            job_dirs.add(dir_name)
    
    for job_dir_name in job_dirs:
        # Check if summary file already exists
        summary_file_path = f"{job_dir_name}/daily_news.txt"
        if storage.file_exists(summary_file_path) and not force:
            logger.info(f"Summary already exists for {job_dir_name}, skipping...")
        else:
            # Pass job directory name directly to summarizer
            summarizer.generate_summary_from_job_dir(job_dir_name)


def validate_step_combinations(steps: list[Steps]) -> None:
    """
    Validate that step combinations are logically consistent.
    
    Args:
        steps: List of Steps to validate
        
    Raises:
        ValueError: If step combinations are invalid
    """
    step_values = [step.value for step in steps]
    
    # Check for conflicting harvest steps
    if Steps.HARVEST.value in step_values:
        if Steps.HARVEST_SCRAPE.value in step_values:
            raise ValueError("Cannot combine 'harvest' with 'harvest_scrape' - harvest includes scraping")
        if Steps.HARVEST_CLEAN.value in step_values:
            raise ValueError("Cannot combine 'harvest' with 'harvest_clean' - harvest includes cleaning")
    
    # Check for harvest_clean without preceding harvest_scrape (when not using harvest)
    if (Steps.HARVEST_CLEAN.value in step_values and 
        Steps.HARVEST.value not in step_values and 
        Steps.HARVEST_SCRAPE.value not in step_values):
        logger.warning("Running 'harvest_clean' without 'harvest_scrape' - ensure scraped content exists in the job directory")


async def scrape(sites: list[str]) -> str:
    """
    Execute the scraping phase only.
    
    Args:
        sites: List of sites to scrape
        
    Returns:
        str: The job directory path created for the scraped content
    """
    logger.info(f"Starting scrape-only operation for {len(sites)} sites")
    harvester: Harvester = Harvester()
    job_dir = await harvester.scrape_sites(sites=sites)
    return job_dir


async def clean(job_dir: str, sites: list[str]) -> None:
    """
    Execute the cleaning phase only.
    
    Args:
        job_dir: The job directory containing scraped content
        sites: List of sites to clean
    """
    logger.info(f"Starting clean-only operation for {len(sites)} sites in {job_dir}")
    harvester: Harvester = Harvester()
    await harvester.clean_sites(job_dir=job_dir, sites=sites)

async def run(steps: list[Steps], **kwargs) -> dict:
    """
    Execute the media lens pipeline with the specified steps.
    
    Args:
        steps: List of Steps to execute
        **kwargs: Additional arguments
        
    Returns:
        dict: Status information about the run
    """
    # Validate step combinations before starting
    validate_step_combinations(steps)
    
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
    
    # Storage adapter handles directory creation automatically

    if 'job_dir' not in kwargs or kwargs['job_dir'] == "latest":
        # Find the latest job directory using JobDir class
        latest_job = JobDir.find_latest(storage)
        artifacts_dir = latest_job.storage_path if latest_job else None
    else:
        job_dir_path = kwargs['job_dir']
        try:
            # Validate the specified job directory
            job_dir = JobDir.from_path(job_dir_path)
            artifacts_dir = job_dir.storage_path
        except ValueError:
            raise ValueError(f"Invalid job directory format: {job_dir_path}")

    try:
        if Steps.HARVEST in steps and not RunState.stop_requested():
            # Harvest (complete workflow: scrape + clean)
            logger.info(f"[Run {run_id}] Starting harvest step")
            harvester: Harvester = Harvester()
            # reassign artifacts_dir to new dir (harvest now returns string)
            artifacts_dir = await harvester.harvest(sites=SITES)
            result["completed_steps"].append(Steps.HARVEST.value)
            
        elif Steps.HARVEST_SCRAPE in steps and not RunState.stop_requested():
            # Harvest Scrape (scraping only)
            logger.info(f"[Run {run_id}] Starting harvest scrape step")
            artifacts_dir = await scrape(sites=SITES)
            result["completed_steps"].append(Steps.HARVEST_SCRAPE.value)
            
        elif Steps.REHARVEST in steps and not RunState.stop_requested():
            # Re-Harvest
            logger.info(f"[Run {run_id}] Starting re-harvest step")
            harvester: Harvester = Harvester()
            await harvester.re_harvest(sites=SITES, job_dir=artifacts_dir)
            result["completed_steps"].append(Steps.REHARVEST.value)
            
        if Steps.HARVEST_CLEAN in steps and not RunState.stop_requested():
            # Harvest Clean (cleaning only)
            logger.info(f"[Run {run_id}] Starting harvest clean step")
            if not artifacts_dir:
                raise ValueError("No job directory available for cleaning. Run harvest_scrape first or specify job_dir.")
            await clean(job_dir=artifacts_dir, sites=SITES)
            result["completed_steps"].append(Steps.HARVEST_CLEAN.value)

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
            await interpret_weekly(current_week_only=True, overwrite=True)
            result["completed_steps"].append(Steps.INTERPRET_WEEKLY.value)

        if Steps.SUMMARIZE_DAILY in steps and not RunState.stop_requested():
            # Summarize daily content
            logger.info(f"[Run {run_id}] Starting daily summarization step")
            summarizer: DailySummarizer = DailySummarizer(agent=create_agent_from_env())
            summarizer.generate_summary_from_job_dir(artifacts_dir)
            result["completed_steps"].append(Steps.SUMMARIZE_DAILY.value)

        if Steps.FORMAT in steps and not RunState.stop_requested():
            # Format output
            logger.info(f"[Run {run_id}] Starting format step")
            force_full_format = kwargs.get('force_full_format', False)
            await format_output(force_full=force_full_format)
            result["completed_steps"].append(Steps.FORMAT.value)

        if Steps.DEPLOY in steps and not RunState.stop_requested():
            # Deploy output
            logger.info(f"[Run {run_id}] Starting deployment step")
            force_full_deploy = kwargs.get('force_full_deploy', False)
            await deploy_output(force_full=force_full_deploy)
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
    # Initialize secrets at startup
    from src.media_lens.common import ensure_secrets_loaded
    ensure_secrets_loaded()
    
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
        '--run-id',
        type=str,
        help='Optional run ID for tracking (auto-generated if not provided)'
    )
    run_parser.add_argument(
        '--start-date',
        type=str,
        help='Start date for processing jobs in YYYY-MM-DD format (inclusive)'
    )
    run_parser.add_argument(
        '--end-date',
        type=str,
        help='End date for processing jobs in YYYY-MM-DD format (inclusive)'
    )
    run_parser.add_argument(
        "--sites",
        nargs='+',
        help="List of sites to include"
    )  # Accepts multiple sites
    run_parser.add_argument(
        '--playwright-mode',
        choices=['local', 'cloud'],
        help='Playwright browser configuration mode (default: cloud, or PLAYWRIGHT_MODE env var)'
    )
    run_parser.add_argument(
        '--force-full-format',
        action='store_true',
        help='Force full regeneration of HTML files, ignoring format cursor'
    )
    run_parser.add_argument(
        '--force-full-deploy',
        action='store_true',
        help='Force deployment of all files, ignoring deploy cursor'
    )
    run_parser.add_argument(
        '--rewind-days',
        type=int,
        help='Rewind format and deploy cursors by specified number of days before running'
    )


    # Summarize daily news command with option to force resummarization if no summary present
    summarize_parser = subparsers.add_parser('summarize', help='Summarize daily news')
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
        '--no-overwrite',
        action='store_true',
        help='Do not overwrite existing weekly interpretations'
    )
    
    # Stop command
    stop_parser = subparsers.add_parser('stop', help='Stop a currently running workflow')
    
    # Reset cursor command
    reset_cursor_parser = subparsers.add_parser('reset-cursor', help='Reset format and/or deploy cursors')
    reset_cursor_parser.add_argument(
        '--format',
        action='store_true',
        help='Reset the format cursor (forces full HTML regeneration on next format)'
    )
    reset_cursor_parser.add_argument(
        '--deploy',
        action='store_true',
        help='Reset the deploy cursor (forces full deployment on next deploy)'
    )
    reset_cursor_parser.add_argument(
        '--all',
        action='store_true',
        help='Reset both format and deploy cursors'
    )
    
    # Audit command
    audit_parser = subparsers.add_parser('audit', help='Audit directories for missing or incomplete files')
    audit_parser.add_argument(
        '-s', '--start-date',
        type=str,
        help='Start date in YYYY-MM-DD format (inclusive). If not specified, audits from earliest date.'
    )
    audit_parser.add_argument(
        '-e', '--end-date',
        type=str,
        help='End date in YYYY-MM-DD format (inclusive). If not specified, audits to latest date.'
    )
    audit_parser.add_argument(
        '--no-report',
        action='store_true',
        help='Skip generating the audit report file (audit.txt)'
    )

    global SITES

    # Load environment variables first
    dotenv.load_dotenv()
    
    args = parser.parse_args()
    # Use string path for logger
    log_path = str(get_working_dir() / "runner.log")
    create_logger(LOGGER_NAME, log_path)

    if args.command == 'run':
        steps = [Steps(step) for step in args.steps]
        if args.sites:
            SITES = args.sites
        
        # Handle playwright mode: CLI arg overrides env var, default to 'cloud'
        if hasattr(args, 'playwright_mode') and args.playwright_mode:
            # CLI argument provided
            playwright_mode = args.playwright_mode
        else:
            # Use environment variable or default to 'cloud'
            playwright_mode = os.getenv('PLAYWRIGHT_MODE', 'cloud')
        
        os.environ['PLAYWRIGHT_MODE'] = playwright_mode
        logger.info(f"Using Playwright mode: {playwright_mode}")

        logger.info(f"Using sites: {', '.join(SITES)}")
        
        # Handle cursor rewind if specified
        if hasattr(args, 'rewind_days') and args.rewind_days:
            days = args.rewind_days
            logger.info(f"Rewinding cursors by {days} days")
            rewind_format_cursor(days)
            rewind_deploy_cursor(days)
        
        # Handle date range processing
        if args.start_date or args.end_date:
            if not args.start_date or not args.end_date:
                logger.error("Both --start-date and --end-date must be provided when using date range")
                return
            
            # Get job directories in date range
            job_dirs = storage.get_jobs_in_date_range(args.start_date, args.end_date)
            if not job_dirs:
                logger.warning(f"No job directories found in date range {args.start_date} to {args.end_date}")
                return
            
            logger.info(f"Processing {len(job_dirs)} job directories in date range")
            for job_dir in job_dirs:
                logger.info(f"Processing job directory: {job_dir}")
                run_result = asyncio.run(run(
                    steps=steps, 
                    job_dir=job_dir,
                    run_id=args.run_id if hasattr(args, 'run_id') and args.run_id else None,
                    force_full_format=getattr(args, 'force_full_format', False),
                    force_full_deploy=getattr(args, 'force_full_deploy', False)
                ))
                if run_result["status"] != "success":
                    logger.warning(f"Job {job_dir} completed with status: {run_result['status']}")
        else:
            run_result = asyncio.run(run(
                steps=steps, 
                job_dir=args.job_dir,
                run_id=args.run_id if hasattr(args, 'run_id') and args.run_id else None,
                force_full_format=getattr(args, 'force_full_format', False),
                force_full_deploy=getattr(args, 'force_full_deploy', False)
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
        force = args.force
        if force:
            logger.info("Force resummarization of daily news")
            asyncio.run(summarize_all())
        else:
            logger.info("Summarizing daily news without force")
            asyncio.run(summarize_all())
    elif args.command == 'reinterpret-weeks':
        # Reinterpret weekly content from a specified date
        try:
            start_date = strptime(args.date, "%Y-%m-%d")
            start_date = start_date.replace(tzinfo=datetime.timezone.utc)
            logger.info(f"Reinterpreting weekly content from {args.date}")
            
            asyncio.run(reinterpret_weeks_from_date(
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
    elif args.command == 'reset-cursor':
        # Reset cursors
        if args.all or (not args.format and not args.deploy):
            # Reset both if --all specified or no specific cursor mentioned
            reset_format_cursor()
            reset_deploy_cursor()
            print("Both format and deploy cursors have been reset")
        else:
            if args.format:
                reset_format_cursor()
                print("Format cursor has been reset")
            if args.deploy:
                reset_deploy_cursor()
                print("Deploy cursor has been reset")
    elif args.command == 'audit':
        # Audit directories for completeness
        start_date = None
        end_date = None
        
        if args.start_date:
            try:
                start_date = strptime(args.start_date, "%Y-%m-%d")
                start_date = start_date.replace(tzinfo=datetime.timezone.utc)
            except ValueError as e:
                logger.error(f"Invalid start date format: {str(e)}")
                print(f"Error: Invalid start date format. Use YYYY-MM-DD")
                return
                
        if args.end_date:
            try:
                end_date = strptime(args.end_date, "%Y-%m-%d")
                end_date = end_date.replace(tzinfo=datetime.timezone.utc)
            except ValueError as e:
                logger.error(f"Invalid end date format: {str(e)}")
                print(f"Error: Invalid end date format. Use YYYY-MM-DD")
                return
        
        generate_report = not args.no_report
        logger.info(f"Starting audit from {args.start_date if args.start_date else 'earliest'} to {args.end_date if args.end_date else 'latest'}")
        audit_days(start_date=start_date, end_date=end_date, audit_report=generate_report)
        print("Audit completed successfully")
    else:
        parser.print_help()

if __name__ == '__main__':
    main()