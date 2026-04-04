#!/usr/bin/env python3
"""
Recover March 23, 2026 front pages from Internet Archive using direct URL attempts.
Avoids CDX API rate limiting by trying common snapshot times directly.
"""

import requests
import logging
from pathlib import Path
import time
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SITES = ["www.cnn.com", "www.bbc.com", "www.foxnews.com"]
JOB_DIR = Path("/Users/dan/dev/code/projects/python/media_lens/working/out/jobs/2026/03/23/160000")

# Try these timestamps in order for March 23, 2026 (9 AM PT = 16-17 UTC)
TIMESTAMPS_TO_TRY = [
    "20260323160000",  # 16:00 UTC
    "20260323150000",  # 15:00 UTC
    "20260323170000",  # 17:00 UTC
    "20260323140000",  # 14:00 UTC
    "20260323180000",  # 18:00 UTC
]

def try_snapshot(site: str, timestamp: str) -> str | None:
    """Try to fetch a specific snapshot, return HTML if successful."""
    url = f"https://web.archive.org/web/{timestamp}id_/https://{site}"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200 and len(response.text) > 50000:  # Sanity check
            logger.info(f"✓ Success: {site} at {timestamp} ({len(response.text)} bytes)")
            return response.text
        else:
            logger.debug(f"✗ Failed {site} at {timestamp}: status {response.status_code}, size {len(response.text)}")
            return None
    except Exception as e:
        logger.debug(f"✗ Error {site} at {timestamp}: {e}")
        return None

def main():
    logger.info(f"Recovering March 23, 2026 snapshots (direct method)")
    logger.info(f"Job directory: {JOB_DIR}\n")

    JOB_DIR.mkdir(parents=True, exist_ok=True)

    for site in SITES:
        logger.info(f"\nFetching {site}...")
        found = False

        for timestamp in TIMESTAMPS_TO_TRY:
            if found:
                break

            html = try_snapshot(site, timestamp)
            if html:
                output_path = JOB_DIR / f"{site}.html"
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info(f"Saved {site} from {timestamp} to {output_path}")
                found = True
                time.sleep(random.uniform(3, 5))
                break

            time.sleep(random.uniform(1, 2))

        if not found:
            logger.error(f"Could not find snapshot for {site}")

    logger.info(f"\n{'='*60}")
    logger.info(f"Download complete!")
    logger.info(f"Next, run: uv run python -m src.media_lens.runner run -s harvest_clean extract interpret_weekly format deploy -j jobs/2026/03/23/160000")
    logger.info(f"{'='*60}")

if __name__ == "__main__":
    main()
