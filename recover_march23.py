#!/usr/bin/env python3
"""
Recover March 23, 2026 from Internet Archive using archive.org API.
Uses the same cleaners as media_lens to properly process the HTML.
"""
import os
import sys
import requests
import logging
import time
from pathlib import Path

# Add project root to sys.path
project_root = "/Users/dan/dev/code/projects/python/media_lens"
if project_root not in sys.path:
    sys.path.append(project_root)

from src.media_lens.collection.cleaner import WebpageCleaner, CNNCleaner, BBCCleaner, FoxNewsCleaner

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("recover_march23")

# Configuration
DATE = "2026-03-23"
TARGET_HOUR_UTC = 16  # 9 AM PT = 16 UTC (PDT)
JOB_DIR = Path("/Users/dan/dev/code/projects/python/media_lens/working/out/jobs/2026/03/23/160000")

SITES = {
    "www.cnn.com": CNNCleaner(),
    "www.bbc.com": BBCCleaner(),
    "www.foxnews.com": FoxNewsCleaner()
}

def fetch_wayback_snapshot(url: str, date_str: str, hour_utc: int = 16) -> str | None:
    """
    Fetch snapshot from Internet Archive using archive.org API.
    Uses the same mechanism as recover_missing_days.py
    """
    # Try multiple timestamps around the target hour
    timestamps_to_try = [
        f"{date_str.replace('-', '')}{hour_utc:02d}0000",      # Target hour
        f"{date_str.replace('-', '')}{hour_utc-1:02d}0000",    # Hour before
        f"{date_str.replace('-', '')}{hour_utc+1:02d}0000",    # Hour after
    ]

    for timestamp in timestamps_to_try:
        try:
            api_url = f"http://archive.org/wayback/available?url={url}&timestamp={timestamp}"
            logger.info(f"Querying archive.org API for {url} at {timestamp}")

            resp = requests.get(api_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            snapshots = data.get("archived_snapshots", {})
            if "closest" in snapshots:
                snapshot_url = snapshots["closest"]["url"]
                logger.info(f"Found snapshot: {snapshot_url}")

                # Ensure raw HTML by using 'id_' mode
                if "id_" not in snapshot_url:
                    parts = snapshot_url.split("/")
                    for i, p in enumerate(parts):
                        if p.isdigit() and len(p) >= 14:
                            parts[i] = p + "id_"
                            break
                    snapshot_url = "/".join(parts)

                # Add significant delay before downloading to avoid rate limiting
                logger.info(f"Waiting 30s before downloading to avoid rate limiting...")
                time.sleep(30)

                logger.info(f"Downloading from {snapshot_url}")
                content_resp = requests.get(snapshot_url, timeout=90)
                content_resp.raise_for_status()

                if len(content_resp.text) > 50000:  # Sanity check
                    logger.info(f"Successfully fetched {len(content_resp.text)} bytes from {timestamp}")
                    return content_resp.text
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning(f"Rate limited (429) for {url} at {timestamp}, waiting 60s...")
                time.sleep(60)
            else:
                logger.warning(f"Failed to fetch {url} at {timestamp}: {e}")
                time.sleep(5)
        except Exception as e:
            logger.warning(f"Failed to fetch {url} at {timestamp}: {e}")
            time.sleep(5)

    return None

def process_day():
    """Download and clean all sites for March 23."""
    logger.info(f"Recovering March 23, 2026 from Internet Archive")
    logger.info(f"Target hour: {TARGET_HOUR_UTC}:00 UTC")
    logger.info(f"Job directory: {JOB_DIR}\n")

    JOB_DIR.mkdir(parents=True, exist_ok=True)

    for site, cleaner_obj in SITES.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {site}")
        logger.info(f"{'='*60}")

        try:
            # Fetch raw HTML from Wayback Machine
            html_content = fetch_wayback_snapshot(f"https://{site}", DATE, TARGET_HOUR_UTC)

            if not html_content:
                logger.error(f"Failed to fetch {site}")
                continue

            # Save raw HTML
            raw_file = JOB_DIR / f"{site}.html"
            with open(raw_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"Saved raw HTML: {raw_file} ({len(html_content)} bytes)")

            # Clean HTML using media_lens cleaner
            cleaner = WebpageCleaner(cleaner_obj)
            cleaned = cleaner.clean_html(html_content)
            cleaned = cleaner.filter_text_elements(cleaned)

            clean_file = JOB_DIR / f"{site}-clean.html"
            with open(clean_file, "w", encoding="utf-8") as f:
                f.write(cleaned)
            logger.info(f"Saved cleaned HTML: {clean_file} ({len(cleaned)} bytes)")

            time.sleep(3)  # Be nice to the API

        except Exception as e:
            logger.error(f"Failed to process {site}: {e}")
            import traceback
            traceback.print_exc()

    logger.info(f"\n{'='*60}")
    logger.info(f"Recovery complete!")
    logger.info(f"Raw and cleaned HTML files ready in: {JOB_DIR}")
    logger.info(f"\nNext, run the pipeline:")
    logger.info(f"  cd {project_root}")
    logger.info(f"  uv run python -m src.media_lens.runner run -s extract interpret_weekly summarize_daily format deploy -j jobs/2026/03/23/160000")
    logger.info(f"{'='*60}\n")

if __name__ == "__main__":
    process_day()
