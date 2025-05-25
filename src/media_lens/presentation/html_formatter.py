import datetime
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Any, Union
from urllib.parse import urlparse

import dotenv
from jinja2 import Environment, FileSystemLoader
from src.media_lens.storage import shared_storage
import datetime

from src.media_lens.common import (
    UTC_REGEX_PATTERN_BW_COMPAT, LOGGER_NAME, SITES, get_project_root,
    timestamp_as_long_date, timestamp_bw_compat_str_as_long_date, get_utc_datetime_from_timestamp, get_week_key, get_week_display
)

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
    logger.debug(f"Generating HTML with template {template_name} in path {template_dir_path}")
    env = Environment(loader=FileSystemLoader(template_dir_path))
    template = env.get_template(template_name)
    html_output = template.render(**content)
    return html_output


def organize_runs_by_week(job_dirs: List[Path], sites: List[str]) -> Dict[str, Any]:
    """
    Organize job runs by calendar week.
    
    :param job_dirs: List of job directories
    :param sites: List of media sites
    :return: Dictionary with weeks as keys and runs as values
    """
    logger.info(f'Organizing {len(job_dirs)} jobs by week')
    
    # Dictionary to store runs by week
    weeks_data = defaultdict(list)
    
    # Process each job directory
    for job_dir in job_dirs:
        logger.debug(f"Processing job_dir {job_dir}")
        
        # Skip directories that don't match the UTC pattern
        if not re.match(UTC_REGEX_PATTERN_BW_COMPAT, job_dir.name):
            continue
        
        # Get UTC datetime from job directory name
        job_utc_datetime: datetime = get_utc_datetime_from_timestamp(job_dir.name)

        # Get week key for this job (e.g., "2025-W08")
        week_key: str = get_week_key(job_utc_datetime)
        
        # Create run data dictionary
        run_data = {
            "run_timestamp": timestamp_bw_compat_str_as_long_date(job_dir.name),
            "run_datetime": job_utc_datetime,
            "job_dir": job_dir,
            "sites": sites,
            "extracted": [],
            "interpreted": [],
            "news_summary": "",
        }
        
        # Process each site
        for site in sites:
            storage = shared_storage
            
            # Get job directory name
            job_dir_name = job_dir.name if hasattr(job_dir, 'name') else job_dir
            
            # Load extracted data
            extracted_path = f"{job_dir_name}/{site}-clean-extracted.json"
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
            news_summary_path = f"{job_dir_name}/daily_news.txt"
            if storage.file_exists(news_summary_path):
                news_summary = storage.read_text(news_summary_path)
                run_data['news_summary'] = news_summary.replace("\n", "<br>")

            # Load interpreted data
            interpreted_path = f"{job_dir_name}/{site}-interpreted.json"
            if not storage.file_exists(interpreted_path):
                # this is expected if daily interpretation is not active
                logger.debug(f"Interpreted file not found: {interpreted_path}")
            else:
                interpreted = storage.read_json(interpreted_path)
                run_data['interpreted'].append({
                    'site': site,
                    'qa': interpreted
                })

        # Add this run to the appropriate week
        weeks_data[week_key].append(run_data)
    
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
        storage = shared_storage
        
        # Iterate through weeks (newest first) until we find an available interpretation
        found_valid_weekly = False
        for week in weeks_data["weeks"]:
            week_key = week["week_key"]
            weekly_file_path = f"weekly-{week_key}-interpreted.json"
            
            if storage.file_exists(weekly_file_path):
                try:
                    weekly_data = storage.read_json(weekly_file_path)
                    if isinstance(weekly_data, list):
                        # Process the weekly summary data for the template
                        weekly_summary = []
                        for data in weekly_data:
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
                        
                        # Add weekly summary to index content
                        index_content["weekly_summary"] = weekly_summary
                        index_content["weekly_summary_date"] = week["week_display"].replace("Week of ", "")
                        index_content["sites"] = SITES
                        
                        logger.info(f"Added weekly summary to index page for week {week_key}")
                        found_valid_weekly = True
                        break  # Stop looking after finding first valid weekly summary
                    else:
                        logger.warning(f"Weekly interpretation has wrong format: {weekly_file_path}")
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


def generate_html_from_path(sites: list[str], template_dir_path: Path) -> str:
    """
    Revised method to generate HTML from a path, now handling weekly organization.
    
    :param sites: list of media sites that will be covered
    :param template_dir_path: full path to location of Jinja2 templates
    :return: HTML content for the index page
    """
    logger.info(f"Generating HTML for {len(sites)} sites")
    storage = shared_storage

    # Get all job directories using the storage adapter
    all_dirs = storage.list_directories()
    dir_names = set()
    
    # Filter directory names that match UTC pattern
    for dir_name in all_dirs:
        if re.match(UTC_REGEX_PATTERN_BW_COMPAT, dir_name):
            dir_names.add(dir_name)
                
    # Convert to Path objects for backward compatibility
    dirs = [Path(storage.get_absolute_path(dir_name)) for dir_name in dir_names]
    
    # Organize runs by week
    weeks_data = organize_runs_by_week(dirs, sites)
    
    # Generate weekly HTML files
    weekly_html = generate_weekly_reports(weeks_data, sites, template_dir_path)
    
    # Write weekly HTML files
    for week_key, html in weekly_html.items():
        weekly_file_path = f"medialens-{week_key}.html"
        logger.debug(f"Writing weekly HTML for week {week_key} to {weekly_file_path}")
        storage.write_text(weekly_file_path, html)
    
    # Generate and return index page
    index_html = generate_index_page(weeks_data, template_dir_path)
    storage.write_text("medialens.html", index_html)
    
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
