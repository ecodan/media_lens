import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.media_lens.collection.cleaner import WebpageCleaner, cleaner_for_site
from src.media_lens.collection.harvester import Harvester
from src.media_lens.common import (
    LOGGER_NAME, 
    SITES,
    UTC_DATE_PATTERN_BW_COMPAT,
    get_utc_datetime_from_timestamp,
    ANTHROPIC_MODEL
)
from src.media_lens.extraction.agent import ClaudeLLMAgent
from src.media_lens.extraction.extractor import ContextExtractor
from src.media_lens.storage import shared_storage

logger = logging.getLogger(LOGGER_NAME)


def audit_days(start_date: datetime = None, end_date: datetime = None, audit_report: bool = True) -> None:
    """
    Visit all of the output job directories under the output root directory and ensure completeness.
    Each day should have a complete set of files for each site, including:
    - <site>.html
    - <site>-clean.html
    - <site>-clean-article-extracted.json
    - <site>-clean-article-<number 1..5>.json
    :param start_date: date to start auditing from (inclusive); if None, defaults to earliest date in output root
    :param end_date: date to end auditing at (inclusive); if None, defaults to latest date in output root
    :param audit_report: if True, write an audit report to audit.txt (default: True)
    :return: None
    """
    
    logger.info("Starting audit_days process")
    storage = shared_storage
    
    # Initialize audit report data
    audit_data = {
        "timestamp": datetime.now().isoformat(),
        "start_date": start_date.isoformat() if start_date else "earliest",
        "end_date": end_date.isoformat() if end_date else "latest",
        "directories_audited": [],
        "problems_found": [],
        "repairs_made": [],
        "total_directories": 0,
        "total_problems": 0,
        "total_repairs": 0
    }
    
    # Get all directories in storage that match timestamp pattern
    all_files = storage.list_files("")
    timestamp_dirs = set()
    
    # Extract unique timestamp directories from file paths
    timestamp_pattern = re.compile(r'(\d{4}-\d{2}-\d{2}_\d{6})')
    for file_path in all_files:
        match = timestamp_pattern.match(file_path)
        if match:
            timestamp_dirs.add(match.group(1))
    
    # Filter directories by date range if specified
    filtered_dirs = []
    for timestamp_dir in sorted(timestamp_dirs):
        try:
            dir_datetime = get_utc_datetime_from_timestamp(timestamp_dir)
            
            # Check if within date range
            if start_date and dir_datetime.date() < start_date.date():
                continue
            if end_date and dir_datetime.date() > end_date.date():
                continue
                
            filtered_dirs.append(timestamp_dir)
        except ValueError as e:
            logger.warning(f"Could not parse timestamp from directory {timestamp_dir}: {e}")
            continue
    
    if not filtered_dirs:
        logger.info("No directories found matching the specified date range")
        return
    
    logger.info(f"Auditing {len(filtered_dirs)} directories")
    audit_data["total_directories"] = len(filtered_dirs)
    
    # Audit each directory
    for timestamp_dir in filtered_dirs:
        logger.info(f"Auditing directory: {timestamp_dir}")
        audit_data["directories_audited"].append(timestamp_dir)
        _audit_single_directory(timestamp_dir, SITES, audit_data)
    
    # Calculate final totals
    audit_data["total_problems"] = len(audit_data["problems_found"])
    audit_data["total_repairs"] = len([r for r in audit_data["repairs_made"] if r["success"]])
    
    # Generate audit report if requested
    if audit_report:
        _generate_audit_report(audit_data, storage)


def _audit_single_directory(timestamp_dir: str, sites: List[str], audit_data: dict) -> None:
    """
    Audit a single timestamp directory for completeness.
    
    :param timestamp_dir: The timestamp directory to audit
    :param sites: List of sites to check
    :param audit_data: Dictionary to collect audit information for reporting
    """
    storage = shared_storage
    missing_files = []
    needs_cleaning = []
    needs_extraction = []
    
    for site in sites:
        # Check for required files
        raw_html = f"{timestamp_dir}/{site}.html"
        clean_html = f"{timestamp_dir}/{site}-clean.html"
        extracted_json = f"{timestamp_dir}/{site}-clean-extracted.json"
        
        # Check if raw HTML exists
        if not storage.file_exists(raw_html):
            problem = f"Missing raw HTML file: {raw_html} - nothing to do"
            logger.error(problem)
            missing_files.append(raw_html)
            audit_data["problems_found"].append({
                "directory": timestamp_dir,
                "site": site,
                "type": "missing_raw_html",
                "file": raw_html,
                "description": problem,
                "repairable": False
            })
            continue
            
        # Check if clean HTML exists
        if not storage.file_exists(clean_html):
            problem = f"Missing clean HTML file: {clean_html} - will regenerate"
            logger.warning(problem)
            needs_cleaning.append((timestamp_dir, site))
            audit_data["problems_found"].append({
                "directory": timestamp_dir,
                "site": site,
                "type": "missing_clean_html",
                "file": clean_html,
                "description": problem,
                "repairable": True
            })
            
        # Check if extracted JSON exists
        if not storage.file_exists(extracted_json):
            problem = f"Missing extracted JSON file: {extracted_json} - will regenerate"
            logger.warning(problem)
            needs_extraction.append((timestamp_dir, site))
            audit_data["problems_found"].append({
                "directory": timestamp_dir,
                "site": site,
                "type": "missing_extracted_json",
                "file": extracted_json,
                "description": problem,
                "repairable": True
            })
        else:
            # Check for article files (typically 0-4, but we'll check what exists)
            try:
                extracted_data = storage.read_json(extracted_json)
                stories = extracted_data.get("stories", [])
                for idx, story in enumerate(stories):
                    article_file = f"{timestamp_dir}/{site}-clean-article-{idx}.json"
                    if story.get("url") and not storage.file_exists(article_file):
                        problem = f"Missing article file: {article_file}"
                        logger.warning(problem)
                        audit_data["problems_found"].append({
                            "directory": timestamp_dir,
                            "site": site,
                            "type": "missing_article_file",
                            "file": article_file,
                            "description": problem,
                            "repairable": True
                        })
                        needs_extraction.append((timestamp_dir, site))
                        break  # Only need to flag once per site
            except Exception as e:
                problem = f"Error reading extracted data from {extracted_json}: {e}"
                logger.error(problem)
                audit_data["problems_found"].append({
                    "directory": timestamp_dir,
                    "site": site,
                    "type": "corrupted_extracted_json",
                    "file": extracted_json,
                    "description": problem,
                    "repairable": True
                })
                needs_extraction.append((timestamp_dir, site))
    
    # Note: totals will be calculated after all directories are processed
    
    # Run repair operations
    if needs_cleaning:
        _repair_cleaning(needs_cleaning, audit_data)
    
    if needs_extraction:
        asyncio.run(_repair_extraction(needs_extraction, audit_data))


def _repair_cleaning(needs_cleaning: List[tuple], audit_data: dict) -> None:
    """
    Repair missing clean HTML files.
    
    :param needs_cleaning: List of (timestamp_dir, site) tuples that need cleaning
    :param audit_data: Dictionary to collect audit information for reporting
    """
    storage = shared_storage
    
    for timestamp_dir, site in needs_cleaning:
        try:
            logger.info(f"Repairing clean HTML for {site} in {timestamp_dir}")
            
            # Read the raw HTML
            raw_html_path = f"{timestamp_dir}/{site}.html"
            content = storage.read_text(raw_html_path)
            
            # Clean the content
            cleaner = WebpageCleaner(site_cleaner=cleaner_for_site(site))
            clean_content = cleaner.clean_html(content)
            clean_content = cleaner.filter_text_elements(clean_content)
            
            # Write the cleaned content
            clean_html_path = f"{timestamp_dir}/{site}-clean.html"
            storage.write_text(clean_html_path, clean_content, encoding="utf-8")
            
            logger.info(f"Successfully repaired clean HTML: {clean_html_path}")
            audit_data["repairs_made"].append({
                "directory": timestamp_dir,
                "site": site,
                "type": "repair_clean_html",
                "file": clean_html_path,
                "description": f"Successfully regenerated clean HTML for {site}",
                "success": True
            })
            
        except Exception as e:
            error_msg = f"Failed to repair clean HTML for {site} in {timestamp_dir}: {e}"
            logger.error(error_msg)
            audit_data["repairs_made"].append({
                "directory": timestamp_dir,
                "site": site,
                "type": "repair_clean_html",
                "file": clean_html_path,
                "description": error_msg,
                "success": False
            })


async def _repair_extraction(needs_extraction: List[tuple], audit_data: dict) -> None:
    """
    Repair missing extraction files.
    
    :param needs_extraction: List of (timestamp_dir, site) tuples that need extraction
    :param audit_data: Dictionary to collect audit information for reporting
    """
    storage = shared_storage
    
    # Group by timestamp directory to process efficiently
    dirs_to_process = {}
    for timestamp_dir, site in needs_extraction:
        if timestamp_dir not in dirs_to_process:
            dirs_to_process[timestamp_dir] = []
        dirs_to_process[timestamp_dir].append(site)
    
    # Create extractor with API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not found - cannot run extraction repair")
        return
        
    agent = ClaudeLLMAgent(api_key=api_key, model=ANTHROPIC_MODEL)
    
    for timestamp_dir, sites in dirs_to_process.items():
        try:
            logger.info(f"Repairing extraction for {len(sites)} sites in {timestamp_dir}")
            
            # Create a Path object for the extractor (it expects this)
            # Since we're using storage adapter, we'll create a mock path
            working_dir = Path(storage.get_absolute_path(timestamp_dir))
            
            extractor = ContextExtractor(agent=agent, working_dir=working_dir)
            
            # Run extraction with a delay to avoid rate limiting
            await extractor.run(delay_between_sites_secs=30)
            
            logger.info(f"Successfully repaired extraction for {timestamp_dir}")
            for site in sites:
                audit_data["repairs_made"].append({
                    "directory": timestamp_dir,
                    "site": site,
                    "type": "repair_extraction",
                    "file": f"{timestamp_dir}/{site}-clean-extracted.json",
                    "description": f"Successfully regenerated extraction files for {site}",
                    "success": True
                })
            
        except Exception as e:
            error_msg = f"Failed to repair extraction for {timestamp_dir}: {e}"
            logger.error(error_msg)
            for site in sites:
                audit_data["repairs_made"].append({
                    "directory": timestamp_dir,
                    "site": site,
                    "type": "repair_extraction",
                    "file": f"{timestamp_dir}/{site}-clean-extracted.json",
                    "description": error_msg,
                    "success": False
                })


def _generate_audit_report(audit_data: dict, storage) -> None:
    """
    Generate an audit report and save it to audit.txt.
    
    :param audit_data: Dictionary containing audit information
    :param storage: Storage adapter instance
    """
    report_lines = []
    
    # Header
    report_lines.append("=" * 80)
    report_lines.append("MEDIA LENS AUDIT REPORT")
    report_lines.append("=" * 80)
    report_lines.append(f"Generated: {audit_data['timestamp']}")
    report_lines.append(f"Date Range: {audit_data['start_date']} to {audit_data['end_date']}")
    report_lines.append(f"Directories Audited: {audit_data['total_directories']}")
    report_lines.append(f"Total Problems Found: {audit_data['total_problems']}")
    report_lines.append(f"Total Repairs Made: {audit_data['total_repairs']}")
    report_lines.append("")
    
    # Summary by directory
    report_lines.append("DIRECTORIES AUDITED:")
    report_lines.append("-" * 40)
    for directory in audit_data["directories_audited"]:
        dir_problems = [p for p in audit_data["problems_found"] if p["directory"] == directory]
        dir_repairs = [r for r in audit_data["repairs_made"] if r["directory"] == directory]
        report_lines.append(f"  {directory}: {len(dir_problems)} problems, {len(dir_repairs)} repairs")
    report_lines.append("")
    
    # Problems found
    if audit_data["problems_found"]:
        report_lines.append("PROBLEMS FOUND:")
        report_lines.append("-" * 40)
        for problem in audit_data["problems_found"]:
            report_lines.append(f"  Directory: {problem['directory']}")
            report_lines.append(f"  Site: {problem['site']}")
            report_lines.append(f"  Type: {problem['type']}")
            report_lines.append(f"  File: {problem['file']}")
            report_lines.append(f"  Description: {problem['description']}")
            report_lines.append(f"  Repairable: {'Yes' if problem['repairable'] else 'No'}")
            report_lines.append("")
    else:
        report_lines.append("PROBLEMS FOUND: None")
        report_lines.append("")
    
    # Repairs made
    if audit_data["repairs_made"]:
        report_lines.append("REPAIRS MADE:")
        report_lines.append("-" * 40)
        for repair in audit_data["repairs_made"]:
            status = "SUCCESS" if repair["success"] else "FAILED"
            report_lines.append(f"  [{status}] Directory: {repair['directory']}")
            report_lines.append(f"  Site: {repair['site']}")
            report_lines.append(f"  Type: {repair['type']}")
            report_lines.append(f"  File: {repair['file']}")
            report_lines.append(f"  Description: {repair['description']}")
            report_lines.append("")
    else:
        report_lines.append("REPAIRS MADE: None")
        report_lines.append("")
    
    # Footer
    report_lines.append("=" * 80)
    report_lines.append("END OF AUDIT REPORT")
    report_lines.append("=" * 80)
    
    # Write report to storage
    report_content = "\n".join(report_lines)
    report_path = "audit.txt"
    storage.write_text(report_path, report_content)
    
    logger.info(f"Audit report written to: {storage.get_absolute_path(report_path)}")
    print(f"Audit report saved to: {storage.get_absolute_path(report_path)}")