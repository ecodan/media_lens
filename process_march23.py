#!/usr/bin/env python3
"""
Process March 23, 2026 wayback snapshots through media_lens pipeline.
"""
import os
import sys
import logging
from pathlib import Path

os.environ["LOCAL_STORAGE_PATH"] = "/Users/dan/dev/code/projects/python/media_lens/working"

# Add project root to sys.path
project_root = "/Users/dan/dev/code/projects/python/media_lens"
if project_root not in sys.path:
    sys.path.append(project_root)

from src.media_lens.collection.cleaner import WebpageCleaner, CNNCleaner, BBCCleaner, FoxNewsCleaner

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("process_march23")

WAYBACK_DIR = Path("/Users/dan/dev/code/projects/python/media_lens/working/wayback/2026/03/23/170000")
JOB_DIR = Path("/Users/dan/dev/code/projects/python/media_lens/working/out/jobs/2026/03/23/160000")

SITES = {
    "www.cnn.com": CNNCleaner(),
    "www.bbc.com": BBCCleaner(),
    "www.foxnews.com": FoxNewsCleaner()
}

def process_march23():
    """Clean wayback HTML and save to job directory."""
    logger.info(f"Processing March 23, 2026 wayback snapshots")
    logger.info(f"Source: {WAYBACK_DIR}")
    logger.info(f"Destination: {JOB_DIR}\n")

    JOB_DIR.mkdir(parents=True, exist_ok=True)

    for site, cleaner_obj in SITES.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {site}")
        logger.info(f"{'='*60}")

        raw_file = WAYBACK_DIR / f"{site}.html"

        if not raw_file.exists():
            logger.error(f"Source file not found: {raw_file}")
            continue

        try:
            # Read raw HTML
            with open(raw_file, "r", encoding="utf-8") as f:
                html_content = f.read()

            logger.info(f"Read {len(html_content)} bytes from {raw_file.name}")

            # Copy raw HTML to job directory
            job_raw_file = JOB_DIR / f"{site}.html"
            with open(job_raw_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"Copied raw HTML to {job_raw_file}")

            # Clean HTML using media_lens cleaner
            cleaner = WebpageCleaner(cleaner_obj)
            cleaned = cleaner.clean_html(html_content)
            cleaned = cleaner.filter_text_elements(cleaned)

            job_clean_file = JOB_DIR / f"{site}-clean.html"
            with open(job_clean_file, "w", encoding="utf-8") as f:
                f.write(cleaned)

            logger.info(f"Saved cleaned HTML: {job_clean_file} ({len(cleaned)} bytes)")

        except Exception as e:
            logger.error(f"Failed to process {site}: {e}")
            import traceback
            traceback.print_exc()

    logger.info(f"\n{'='*60}")
    logger.info(f"Processing complete!")
    logger.info(f"Raw and cleaned HTML files ready in: {JOB_DIR}")
    logger.info(f"\nNext, run the pipeline from the VM:")
    logger.info(f"  curl -X POST http://localhost:8080/run \\")
    logger.info(f"    -H 'Content-Type: application/json' \\")
    logger.info(f"    -d '{{\"steps\": [\"extract\", \"interpret_weekly\", \"summarize_daily\", \"format\", \"deploy\"], \"job_dir\": \"jobs/2026/03/23/160000\"}}'")
    logger.info(f"{'='*60}\n")

if __name__ == "__main__":
    process_march23()
