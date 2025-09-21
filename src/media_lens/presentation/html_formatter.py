import datetime
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Any, Union, Optional
from urllib.parse import urlparse

import dotenv
from jinja2 import Environment, FileSystemLoader
from src.media_lens.storage import shared_storage
import datetime

from src.media_lens.common import (
    UTC_REGEX_PATTERN_BW_COMPAT, LOGGER_NAME, SITES, get_project_root,
    timestamp_as_long_date, timestamp_bw_compat_str_as_long_date, get_utc_datetime_from_timestamp, get_week_key, get_week_display
)
from src.media_lens.job_dir import JobDir
from src.media_lens.storage_adapter import StorageAdapter

logger = logging.getLogger(LOGGER_NAME)


def convert_relative_url(url: str, site: str) -> str:
    """
    Process a potentially relative URL, adding https:// and domain if needed.
    :param url: The URL to process
    :param site: Domain name (e.g., 'www.cnn.com')
    :returns str: Processed URL with protocol and domain if needed
    """
    if not url:
        return url
    # Check if URL already has a protocol
    parsed_url = urlparse(url)
    if parsed_url.scheme:
        return url

    # Append https:// and domain to the relative URL
    url_path = url[1:] if url.startswith('/') else url
    return f'https://{site}/{url_path}'


def generate_html_with_template(template_dir_path: Path, template_name: str, content: dict) -> str:
    """
    Generate HTML using a Jinja2 template.
    """
    # logger.debug(f"Generating HTML with template {template_name} in path {template_dir_path}")
    env = Environment(loader=FileSystemLoader(template_dir_path))
    template = env.get_template(template_name)
    html_output = template.render(**content)
    return html_output


def organize_runs_by_week(job_dirs: List[Union[Path, str, JobDir]], sites: List[str]) -> Dict[str, Any]:
    """
    Organize job runs by calendar week.
    
    :param job_dirs: List of job directories (strings, Paths, or JobDir objects)
    :param sites: List of media sites
    :return: Dictionary with weeks as keys and runs as values
    """
    logger.info(f'Organizing {len(job_dirs)} jobs by week')
    
    # Dictionary to store runs by week
    weeks_data = defaultdict(list)
    
    # Process each job directory
    for job_dir_input in job_dirs:
        logger.debug(f"Processing job_dir {job_dir_input}")
        
        # Convert to JobDir if needed
        if isinstance(job_dir_input, JobDir):
            job_dir = job_dir_input
        else:
            # Handle string/Path inputs
            if isinstance(job_dir_input, Path):
                job_dir_str = job_dir_input.name
            else:
                job_dir_str = str(job_dir_input)
            
            try:
                job_dir = JobDir.from_path(job_dir_str)
            except ValueError:
                logger.debug(f"Skipping invalid job directory: {job_dir_str}")
                continue

        # Create run data dictionary
        run_data = {
            "run_timestamp": timestamp_bw_compat_str_as_long_date(job_dir.timestamp_str),
            "run_datetime": job_dir.datetime,
            "job_dir": job_dir.storage_path,  # Store as string for storage adapter compatibility
            "sites": sites,
            "extracted": [],
            "interpreted": [],
            "news_summary": "",
        }
        
        # Process each site
        for site in sites:
            storage = shared_storage
            
            # Load extracted data
            extracted_path = f"{job_dir.storage_path}/{site}-clean-extracted.json"
            if not storage.file_exists(extracted_path):
                logger.warning(f"Extracted file not found: {extracted_path}")
                continue
                
            extracted = storage.read_json(extracted_path)
            stories = extracted.get('stories', [])
            
            # Clean story URLs
            for story in stories:
                story['url'] = convert_relative_url(story['url'], site)
            
            run_data['extracted'].append({
                'site': site,
                'stories': stories
            })

            # Load news summary
            news_summary_path = f"{job_dir.storage_path}/daily_news.txt"
            if storage.file_exists(news_summary_path):
                news_summary = storage.read_text(news_summary_path)
                run_data['news_summary'] = news_summary.replace("\n", "<br>")

            # Load interpreted data
            interpreted_path = f"{job_dir.storage_path}/{site}-interpreted.json"
            if storage.file_exists(interpreted_path):
                interpreted = storage.read_json(interpreted_path)
                run_data['interpreted'].append({
                    'site': site,
                    'qa': interpreted
                })

        # Add this run to the appropriate week
        weeks_data[job_dir.week_key].append(run_data)
    
    # Sort runs within each week by datetime (newest first)
    for week_key in weeks_data:
        weeks_data[week_key] = sorted(
            weeks_data[week_key], 
            key=lambda x: x["run_datetime"], 
            reverse=True
        )
    
    # Create the final structure
    result = {
        "report_timestamp": timestamp_as_long_date(),
        "weeks": []
    }
    
    # Convert defaultdict to sorted list of weeks
    for week_key in sorted(weeks_data.keys(), reverse=True):
        result["weeks"].append({
            "week_key": week_key,
            "week_display": get_week_display(week_key),
            "runs": weeks_data[week_key]
        })
    
    return result


def generate_weekly_content(week_data: Dict, sites: List[str]) -> Dict:
    """
    Process all runs in a week to create a weekly summary.
    
    :param week_data: Dictionary containing all runs for a week
    :param sites: List of media sites
    :return: Processed weekly content
    """
    # Create site-specific content collections
    site_content = {site: [] for site in sites}
    
    # Collect content from all runs
    for run in week_data["runs"]:
        for extracted in run["extracted"]:
            site = extracted["site"]
            if site in site_content:
                for story in extracted["stories"]:
                    # Add timestamp to help with sorting/organization
                    story["timestamp"] = run["run_timestamp"]
                    story["datetime"] = run["run_datetime"]
                    site_content[site].append(story)
    
    # Sort content for each site by datetime (newest first)
    for site in site_content:
        site_content[site] = sorted(
            site_content[site],
            key=lambda x: x["datetime"],
            reverse=True
        )
    
    # Format for template (without the weekly interpretation section)
    return {
        "week_key": week_data["week_key"],
        "week_display": week_data["week_display"],
        "sites": sites,
        "site_content": site_content,
        "runs": week_data["runs"]
    }


def generate_weekly_reports(weeks_data: Dict, sites: List[str], template_dir_path: Path) -> Dict[str, str]:
    """
    Generate HTML reports for each week.
    
    :param weeks_data: Dictionary containing data organized by week
    :param sites: List of media sites
    :param template_dir_path: Path to templates directory
    :return: Dictionary mapping week keys to HTML content
    """
    weekly_html = {}
    
    # Generate HTML for each week
    for week in weeks_data["weeks"]:
        week_content = generate_weekly_content(week, sites)
        weekly_html[week["week_key"]] = generate_html_with_template(
            template_dir_path,
            "weekly_template.j2",
            week_content
        )
    
    return weekly_html


def generate_index_page(weeks_data: Dict, template_dir_path: Path) -> str:
    """
    Generate an index page with links to all weekly reports and the latest weekly summary.
    
    :param weeks_data: Dictionary containing data organized by week
    :param template_dir_path: Path to templates directory
    :return: HTML content for the index page
    """
    # Create base content dictionary
    index_content = {
        "report_timestamp": weeks_data["report_timestamp"],
        "weeks": weeks_data["weeks"]
    }
    
    # Get the current date and check if it's Sunday
    today = datetime.datetime.now(datetime.timezone.utc)
    
    # Try to load the weekly summary for the latest week with fallback
    if weeks_data["weeks"]:
        storage: StorageAdapter = shared_storage
        
        # Iterate through weeks (newest first) until we find an available interpretation
        found_valid_weekly = False
        for week in weeks_data["weeks"]:
            week_key = week["week_key"]
            weekly_file_path = f"{storage.get_intermediate_directory()}/weekly-{week_key}-interpreted.json"
            
            if storage.file_exists(weekly_file_path):
                try:
                    weekly_data = storage.read_json(weekly_file_path)
                    
                    # Handle new format with metadata or old format (just list)
                    interpretation_data = None
                    included_days = None
                    days_count = None
                    
                    if isinstance(weekly_data, dict) and "interpretation" in weekly_data:
                        # New format with metadata
                        interpretation_data = weekly_data.get("interpretation", [])
                        included_days = weekly_data.get("included_days", [])
                        days_count = weekly_data.get("days_count", 0)
                        logger.info(f"Found new format weekly interpretation for {week_key} with {days_count} days: {', '.join(included_days) if included_days else 'none'}")
                    elif isinstance(weekly_data, list):
                        # Old format (just interpretation data)
                        interpretation_data = weekly_data
                        logger.info(f"Found old format weekly interpretation for {week_key}")
                    else:
                        logger.warning(f"Weekly interpretation has unexpected format: {weekly_file_path}")
                        continue
                    
                    if interpretation_data:
                        # Process the weekly summary data for the template
                        weekly_summary = []
                        for data in interpretation_data:
                            question_str = data.get("question", "")
                            site = data.get("site", "")
                            answer = data.get("answer", "")
                            
                            # Find or create a question entry
                            question_entry = next((q for q in weekly_summary if q["question"] == question_str), None)
                            if question_entry is None:
                                question_entry = {"question": question_str, "answers": {}}
                                weekly_summary.append(question_entry)
                            
                            # Add answer for this site
                            if site:
                                question_entry["answers"][site] = answer
                        
                        # Add weekly summary to index content with enhanced metadata
                        index_content["weekly_summary"] = weekly_summary
                        
                        # Create enhanced date display with actual days if available
                        period_type = weekly_data.get("period_type", "iso_week")

                        if included_days and len(included_days) > 0:
                            # Format the included days for display
                            if period_type == "rolling_7_days":
                                # For rolling 7-day analysis, emphasize it's a rolling window
                                if len(included_days) == 1:
                                    date_display = f"Rolling 7-day analysis for {included_days[0]}"
                                else:
                                    date_display = f"Rolling 7-day analysis: {included_days[0]} to {included_days[-1]} ({len(included_days)} days)"
                            else:
                                # For ISO week analysis, use existing format
                                if len(included_days) == 1:
                                    date_display = f"Analysis for {included_days[0]}"
                                elif len(included_days) <= 7:
                                    date_display = f"Analysis for {len(included_days)} days: {included_days[0]} to {included_days[-1]}"
                                else:
                                    date_display = f"Analysis for {len(included_days)} days: {included_days[0]} to {included_days[-1]}"
                        else:
                            # Fallback to original format
                            if period_type == "rolling_7_days":
                                date_display = f"Rolling 7-day analysis for the week of {week['week_display'].replace('Week of ', '')}"
                            else:
                                date_display = f"Analysis for the week of {week['week_display'].replace('Week of ', '')}"
                        
                        index_content["weekly_summary_date"] = date_display
                        index_content["included_days"] = included_days
                        index_content["days_count"] = days_count
                        index_content["period_type"] = period_type
                        index_content["sites"] = SITES
                        
                        logger.info(f"Added weekly summary to index page for week {week_key}")
                        found_valid_weekly = True
                        break  # Stop looking after finding first valid weekly summary
                except (json.JSONDecodeError) as e:
                    logger.warning(f"Could not load weekly interpretation from {weekly_file_path}: {str(e)}")
            else:
                logger.debug(f"Weekly interpretation file not found: {weekly_file_path}")
        if not found_valid_weekly:
            logger.warning("No valid weekly interpretation found for any week")
    
    return generate_html_with_template(
        template_dir_path,
        "index_template.j2",
        index_content
    )


def get_index_metadata() -> Dict[str, Any]:
    """
    Get cached index metadata or create empty structure.
    
    Returns:
        Dict containing weeks metadata and last_updated timestamp
    """
    storage = shared_storage
    metadata_path = f"{storage.get_staging_directory()}/index_metadata.json"
    
    if storage.file_exists(metadata_path):
        try:
            metadata = storage.read_json(metadata_path)
            return metadata
        except Exception as e:
            logger.warning(f"Could not load index metadata: {e}")
    
    # Return empty metadata structure
    return {
        "weeks": [],
        "last_updated": None
    }


def update_index_metadata(affected_weeks_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update index metadata for affected weeks only.
    
    Args:
        affected_weeks_data: Week data for weeks that changed
        
    Returns:
        Complete updated metadata
    """
    storage = shared_storage
    metadata = get_index_metadata()
    
    # Convert existing weeks to dict for easy lookup
    existing_weeks = {week["week_key"]: week for week in metadata["weeks"]}
    
    # Update metadata for affected weeks
    for week in affected_weeks_data["weeks"]:
        week_key = week["week_key"]
        
        # Create lightweight metadata for this week
        week_metadata = {
            "week_key": week_key,
            "week_display": week["week_display"],
            "job_count": len(week["runs"]),
            "latest_job": max(run["run_datetime"].isoformat() for run in week["runs"]) if week["runs"] else None,
            "has_weekly_summary": _check_weekly_summary_exists(week_key)
        }
        
        existing_weeks[week_key] = week_metadata
    
    # Convert back to sorted list (newest first)
    updated_weeks = list(existing_weeks.values())
    updated_weeks.sort(key=lambda x: x["week_key"], reverse=True)
    
    # Update metadata
    metadata["weeks"] = updated_weeks
    metadata["last_updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Save updated metadata
    metadata_path = f"{storage.get_staging_directory()}/index_metadata.json"
    storage.create_directory(storage.get_staging_directory())
    storage.write_json(metadata_path, metadata)
    
    logger.info(f"Updated index metadata for {len(affected_weeks_data['weeks'])} weeks")
    return metadata


def _check_weekly_summary_exists(week_key: str) -> bool:
    """Check if weekly summary exists for given week."""
    storage = shared_storage
    weekly_file_path = f"{storage.get_intermediate_directory()}/weekly-{week_key}-interpreted.json"
    return storage.file_exists(weekly_file_path)


def get_lightweight_weeks_data() -> Dict[str, Any]:
    """
    Get lightweight weeks data for index page without processing job content.
    Only extracts week keys, display names, and job counts.
    
    Returns:
        Dict with weeks data optimized for index page
    """
    storage = shared_storage
    all_job_dirs = JobDir.list_all(storage)
    
    # Group jobs by week and count them
    weeks_dict = defaultdict(list)
    for job_dir in all_job_dirs:
        weeks_dict[job_dir.week_key].append(job_dir)
    
    # Create lightweight week entries
    weeks_list = []
    for week_key, job_dirs in weeks_dict.items():
        # Get week display from week_key
        week_display = get_week_display(week_key)
        
        weeks_list.append({
            "week_key": week_key,
            "week_display": week_display,
            "runs": [{}] * len(job_dirs)  # Template expects runs|length, create empty objects
        })
    
    # Sort by week key (newest first)
    weeks_list.sort(key=lambda x: x["week_key"], reverse=True)
    
    return {
        "report_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "weeks": weeks_list
    }


def generate_index_page_from_metadata(metadata: Dict[str, Any], template_dir_path: Path) -> str:
    """
    Generate index page from lightweight metadata instead of full weeks data.
    
    Args:
        metadata: Index metadata with week summaries
        template_dir_path: Path to templates directory
        
    Returns:
        HTML content for the index page
    """
    storage = shared_storage
    
    # Create base content dictionary
    index_content = {
        "report_timestamp": metadata.get("last_updated", datetime.datetime.now(datetime.timezone.utc).isoformat()),
        "weeks": metadata["weeks"]
    }
    
    # Try to load the weekly summary for the latest week with fallback
    if metadata["weeks"]:
        # Iterate through weeks (newest first) until we find an available interpretation
        found_valid_weekly = False
        for week in metadata["weeks"]:
            if not week.get("has_weekly_summary", False):
                continue
                
            week_key = week["week_key"]
            weekly_file_path = f"{storage.get_intermediate_directory()}/weekly-{week_key}-interpreted.json"
            
            try:
                weekly_data = storage.read_json(weekly_file_path)
                
                # Handle new format with metadata or old format (just list)
                interpretation_data = None
                included_days = None
                days_count = None
                
                if isinstance(weekly_data, dict) and "interpretation" in weekly_data:
                    # New format with metadata
                    interpretation_data = weekly_data.get("interpretation", [])
                    included_days = weekly_data.get("included_days", [])
                    days_count = weekly_data.get("days_count", 0)
                    logger.info(f"Found new format weekly interpretation for {week_key} with {days_count} days: {', '.join(included_days) if included_days else 'none'}")
                elif isinstance(weekly_data, list):
                    # Old format (just interpretation data)
                    interpretation_data = weekly_data
                    logger.info(f"Found old format weekly interpretation for {week_key}")
                else:
                    logger.warning(f"Weekly interpretation has unexpected format: {weekly_file_path}")
                    continue
                
                if interpretation_data:
                    # Process the weekly summary data for the template
                    weekly_summary = []
                    for data in interpretation_data:
                        question_str = data.get("question", "")
                        site = data.get("site", "")
                        answer = data.get("answer", "")
                        
                        # Find or create a question entry
                        question_entry = next((q for q in weekly_summary if q["question"] == question_str), None)
                        if question_entry is None:
                            question_entry = {"question": question_str, "answers": {}}
                            weekly_summary.append(question_entry)
                        
                        # Add answer for this site
                        if site:
                            question_entry["answers"][site] = answer
                    
                    # Add weekly summary to index content with enhanced metadata
                    index_content["weekly_summary"] = weekly_summary
                    
                    # Create enhanced date display with actual days if available
                    period_type = weekly_data.get("period_type", "iso_week")

                    if included_days and len(included_days) > 0:
                        # Format the included days for display
                        if period_type == "rolling_7_days":
                            # For rolling 7-day analysis, emphasize it's a rolling window
                            if len(included_days) == 1:
                                date_display = f"Rolling 7-day analysis for {included_days[0]}"
                            else:
                                date_display = f"Rolling 7-day analysis: {included_days[0]} to {included_days[-1]} ({len(included_days)} days)"
                        else:
                            # For ISO week analysis, use existing format
                            if len(included_days) == 1:
                                date_display = f"Analysis for {included_days[0]}"
                            elif len(included_days) <= 7:
                                date_display = f"Analysis for {len(included_days)} days: {included_days[0]} to {included_days[-1]}"
                            else:
                                date_display = f"Analysis for {len(included_days)} days: {included_days[0]} to {included_days[-1]}"
                    else:
                        # Fallback to original format
                        if period_type == "rolling_7_days":
                            date_display = f"Rolling 7-day analysis for the week of {week['week_display'].replace('Week of ', '')}"
                        else:
                            date_display = f"Analysis for the week of {week['week_display'].replace('Week of ', '')}"
                    
                    index_content["weekly_summary_date"] = date_display
                    index_content["included_days"] = included_days
                    index_content["days_count"] = days_count
                    index_content["period_type"] = period_type
                    index_content["sites"] = SITES
                    
                    logger.info(f"Added weekly summary to index page for week {week_key}")
                    found_valid_weekly = True
                    break  # Stop looking after finding first valid weekly summary
            except (json.JSONDecodeError) as e:
                logger.warning(f"Could not load weekly interpretation from {weekly_file_path}: {str(e)}")
        
        if not found_valid_weekly:
            logger.warning("No valid weekly interpretation found for any week")
    
    return generate_html_with_template(
        template_dir_path,
        "index_template.j2",
        index_content
    )


def get_format_cursor() -> Optional[datetime.datetime]:
    """
    Get the last format cursor timestamp from storage.
    
    Returns:
        Last processed timestamp or None if no cursor exists
    """
    cursor_path = "format_cursor.txt"
    storage = shared_storage
    
    if storage.file_exists(cursor_path):
        try:
            cursor_str = storage.read_text(cursor_path).strip()
            return datetime.datetime.fromisoformat(cursor_str)
        except (ValueError, OSError) as e:
            logger.warning(f"Could not read format cursor: {e}")
            return None
    return None


def update_format_cursor(timestamp: datetime.datetime) -> None:
    """
    Update the format cursor with the latest processed timestamp.
    
    Args:
        timestamp: The timestamp to set as the new cursor
    """
    cursor_path = "format_cursor.txt"
    storage = shared_storage
    
    try:
        storage.write_text(cursor_path, timestamp.isoformat())
        logger.debug(f"Updated format cursor to {timestamp.isoformat()}")
    except Exception as e:
        logger.error(f"Failed to update format cursor: {e}")


def rewind_format_cursor(days: int) -> None:
    """
    Rewind the format cursor by a specified number of days.
    
    Args:
        days: Number of days to rewind the cursor
    """
    current_cursor = get_format_cursor()
    if current_cursor:
        new_cursor = current_cursor - datetime.timedelta(days=days)
        update_format_cursor(new_cursor)
        logger.info(f"Format cursor rewound by {days} days: {current_cursor.isoformat()} → {new_cursor.isoformat()}")
        print(f"Format cursor rewound by {days} days: {current_cursor.isoformat()} → {new_cursor.isoformat()}")
    else:
        logger.warning("No format cursor found - cannot rewind")
        print("No format cursor found - cannot rewind")


def reset_format_cursor() -> None:
    """
    Reset the format cursor to force full regeneration on next run.
    """
    cursor_path = "format_cursor.txt"
    storage = shared_storage
    
    try:
        if storage.file_exists(cursor_path):
            storage.delete_file(cursor_path)
            logger.info("Format cursor reset - next format will process all content")
    except Exception as e:
        logger.error(f"Failed to reset format cursor: {e}")


def get_jobs_since_cursor(sites: list[str], cursor: Optional[datetime.datetime] = None) -> tuple[List[JobDir], List[str]]:
    """
    Get job directories that need processing since the cursor timestamp.
    
    Args:
        sites: List of media sites
        cursor: Cursor timestamp (None means process all)
        
    Returns:
        Tuple of (job_dirs_to_process, affected_week_keys)
    """
    storage = shared_storage
    all_job_dirs = JobDir.list_all(storage)
    
    if cursor is None:
        logger.info("No cursor found - processing all job directories")
        job_dirs_to_process = all_job_dirs
    else:
        logger.info(f"Processing jobs since cursor: {cursor.isoformat()}")
        job_dirs_to_process = [
            job_dir for job_dir in all_job_dirs 
            if job_dir.datetime > cursor
        ]
        logger.info(f"Found {len(job_dirs_to_process)} new jobs since cursor")
    
    # Determine which weeks are affected
    affected_weeks = set()
    for job_dir in job_dirs_to_process:
        affected_weeks.add(job_dir.week_key)
    
    affected_week_keys = list(affected_weeks)
    logger.info(f"Affected weeks: {affected_week_keys}")
    
    return job_dirs_to_process, affected_week_keys


def generate_html_from_path(sites: list[str], template_dir_path: Path, force_full: bool = False) -> str:
    """
    Generate HTML from job directories with incremental processing support.
    
    :param sites: list of media sites that will be covered
    :param template_dir_path: full path to location of Jinja2 templates
    :param force_full: if True, ignore cursor and regenerate everything
    :return: HTML content for the index page
    """
    logger.info(f"Generating HTML for {len(sites)} sites (force_full={force_full})")
    storage = shared_storage

    # Get cursor and determine what needs processing
    cursor = None if force_full else get_format_cursor()
    new_job_dirs, affected_week_keys = get_jobs_since_cursor(sites, cursor)
    
    if not new_job_dirs and cursor is not None:
        logger.info("No new job directories since last format - skipping generation")
        # Still need to return index HTML, so read from staging if available
        staging_dir = storage.get_staging_directory()
        index_file_path = f"{staging_dir}/medialens.html"
        if storage.file_exists(index_file_path):
            return storage.read_text(index_file_path)
        else:
            logger.warning("No existing index file found, falling back to full generation")
            force_full = True
            cursor = None
            new_job_dirs, affected_week_keys = get_jobs_since_cursor(sites, cursor)
    
    # Get job directories for organizing based on cursor mode
    if force_full or cursor is None:
        # Get all job directories for full regeneration
        job_dirs_for_organizing = JobDir.list_all(storage)
        logger.info(f"Full regeneration mode: organizing {len(job_dirs_for_organizing)} job directories")
    else:
        # For incremental mode, we need all jobs from affected weeks for complete week context
        all_job_dirs = JobDir.list_all(storage)
        job_dirs_for_organizing = [
            job_dir for job_dir in all_job_dirs 
            if job_dir.week_key in affected_week_keys
        ]
        logger.info(f"Incremental mode: organizing {len(job_dirs_for_organizing)} job directories from affected weeks {affected_week_keys}")
    
    # Organize runs by week
    weeks_data = organize_runs_by_week(job_dirs_for_organizing, sites)
    
    # Generate weekly HTML files (only for affected weeks if incremental)
    if force_full or cursor is None:
        logger.info("Generating all weekly HTML files")
        weekly_html = generate_weekly_reports(weeks_data, sites, template_dir_path)
        weeks_to_write = weekly_html.keys()
    else:
        logger.info(f"Generating HTML only for affected weeks: {affected_week_keys}")
        # Generate HTML only for affected weeks
        affected_weeks_data = {
            "report_timestamp": weeks_data["report_timestamp"],
            "weeks": [w for w in weeks_data["weeks"] if w["week_key"] in affected_week_keys]
        }
        weekly_html = generate_weekly_reports(affected_weeks_data, sites, template_dir_path)
        weeks_to_write = affected_week_keys
    
    # Write weekly HTML files to staging directory
    staging_dir = storage.get_staging_directory()
    storage.create_directory(staging_dir)
    
    for week_key in weeks_to_write:
        if week_key in weekly_html:
            weekly_file_path = f"{staging_dir}/medialens-{week_key}.html"
            logger.debug(f"Writing weekly HTML for week {week_key} to {weekly_file_path}")
            storage.write_text(weekly_file_path, weekly_html[week_key])
    
    # Generate and return index page to staging directory
    # Use lightweight weeks data for index page navigation (much faster)
    lightweight_weeks_data = get_lightweight_weeks_data()
    index_html = generate_index_page(lightweight_weeks_data, template_dir_path)
    
    index_file_path = f"{staging_dir}/medialens.html"
    storage.write_text(index_file_path, index_html)
    
    # Update cursor with the latest job timestamp if we processed any new jobs
    if new_job_dirs:
        latest_timestamp = max(job_dir.datetime for job_dir in new_job_dirs)
        update_format_cursor(latest_timestamp)
        logger.info(f"Updated format cursor to {latest_timestamp.isoformat()}")
    
    return index_html


#########################################
# TEST
def main():
    template_dir_path: Path = Path(get_project_root() / "config/templates")
    html: str = generate_html_from_path(SITES, template_dir_path)
    # Weekly HTML files and index file are written inside generate_html_from_path

if __name__ == '__main__':
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.INFO)
    main()
