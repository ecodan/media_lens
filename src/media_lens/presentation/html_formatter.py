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
    logger.info(f"Generating HTML with template {template_name} in {template_dir_path}")
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
            # Load extracted data
            extracted_path = job_dir / f"{site}-clean-extracted.json"
            if not extracted_path.exists():
                logger.warning(f"Extracted file not found: {extracted_path}")
                continue
                
            with open(extracted_path, "r") as f:
                extracted = json.load(f)
                stories = extracted.get('stories', [])
                
                # Clean story URLs
                for story in stories:
                    story['url'] = convert_relative_url(story['url'], site)
                
                run_data['extracted'].append({
                    'site': site,
                    'stories': stories
                })

            # Load news summary
            news_summary_path = job_dir / f"daily_news.txt"
            if news_summary_path.exists():
                with open(news_summary_path, "r") as f:
                    news_summary = f.read()
                    run_data['news_summary'] = news_summary.replace("\n", "<br>")

            # Load interpreted data
            interpreted_path = job_dir / f"{site}-interpreted.json"
            if not interpreted_path.exists():
                logger.warning(f"Interpreted file not found: {interpreted_path}")
            else:
                with open(interpreted_path, "r") as f:
                    interpreted = json.load(f)
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


def generate_weekly_content(week_data: Dict, sites: List[str], job_dirs_root: Path) -> Dict:
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
    
    # Load weekly interpretation if available
    weekly_file = Path(job_dirs_root) / f"weekly-{week_data['week_key']}-interpreted.json"
    # list of dict { "question": str, "answers": { "<site>": "<answer>" } }
    weekly_interpretation: List = []

    def get_question_from_list(q: str, questions: List[Dict[str, Any]]) -> Union[Dict, None]:
        for question in questions:
            if question["question"] == q:
                return question
        return None

    if weekly_file.exists():
        try:
            with open(weekly_file, "r") as f:
                weekly_data = json.load(f)
                if isinstance(weekly_data, list):
                    for data in weekly_data:
                        question_str: str = data["question"]
                        question_dict: Dict = get_question_from_list(question_str, weekly_interpretation)
                        if question_dict is None:
                            question_dict = {"question": question_str, "answers": {}}
                            weekly_interpretation.append(question_dict)
                        question_dict["answers"][data['site']] = data["answer"]
                else:
                    logger.warning(f"Weekly interpretation has wrong format: {weekly_file}")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(f"Could not load weekly interpretation from {weekly_file}: {str(e)}")
    
    # Format for template
    return {
        "week_key": week_data["week_key"],
        "week_display": week_data["week_display"],
        "sites": sites,
        "site_content": site_content,
        "interpretation": weekly_interpretation,
        "runs": week_data["runs"]
    }


def generate_weekly_reports(weeks_data: Dict, sites: List[str], template_dir_path: Path, job_dirs_root: Path) -> Dict[str, str]:
    """
    Generate HTML reports for each week.
    
    :param weeks_data: Dictionary containing data organized by week
    :param sites: List of media sites
    :param template_dir_path: Path to templates directory
    :param job_dirs_root: Root directory containing all job directories
    :return: Dictionary mapping week keys to HTML content
    """
    weekly_html = {}
    
    # Generate HTML for each week
    for week in weeks_data["weeks"]:
        week_content = generate_weekly_content(week, sites, job_dirs_root)
        weekly_html[week["week_key"]] = generate_html_with_template(
            template_dir_path,
            "weekly_template.j2",
            week_content
        )
    
    return weekly_html


def generate_index_page(weeks_data: Dict, template_dir_path: Path) -> str:
    """
    Generate an index page with links to all weekly reports.
    
    :param weeks_data: Dictionary containing data organized by week
    :param template_dir_path: Path to templates directory
    :return: HTML content for the index page
    """
    index_content = {
        "report_timestamp": weeks_data["report_timestamp"],
        "weeks": weeks_data["weeks"]
    }
    
    return generate_html_with_template(
        template_dir_path,
        "index_template.j2",  # We'll create this template
        index_content
    )


def generate_html_from_path(job_dirs_root: Path, sites: list[str], template_dir_path: Path) -> str:
    """
    Revised method to generate HTML from a path, now handling weekly organization.
    
    :param job_dirs_root: the parent dir of all job dirs with UTC dates as names
    :param sites: list of media sites that will be covered
    :param template_dir_path: full path to location of Jinja2 templates
    :return: HTML content for the index page
    """
    logger.info(f"Generating HTML for {len(sites)} sites in {job_dirs_root}")
    
    # Get all job directories
    dirs = [
        node for node in job_dirs_root.iterdir() 
        if node.is_dir() and re.match(UTC_REGEX_PATTERN_BW_COMPAT, node.name)
    ]
    
    # Organize runs by week
    weeks_data = organize_runs_by_week(dirs, sites)
    
    # Generate weekly HTML files
    weekly_html = generate_weekly_reports(weeks_data, sites, template_dir_path, job_dirs_root)
    
    # Write weekly HTML files
    for week_key, html in weekly_html.items():
        with open(job_dirs_root / f"medialens-{week_key}.html", "w") as f:
            f.write(html)
    
    # Generate and return index page
    index_html = generate_index_page(weeks_data, template_dir_path)
    with open(job_dirs_root / "medialens.html", "w") as f:
        f.write(index_html)
    
    return index_html


#########################################
# TEST
def main(job_dirs_root: Path):
    template_dir_path: Path = Path(get_project_root() / "config/templates")
    html: str = generate_html_from_path(job_dirs_root, SITES, template_dir_path)
    # Weekly HTML files and index file are written inside generate_html_from_path

if __name__ == '__main__':
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.INFO)
    main(Path(get_project_root() / "working/out"))
