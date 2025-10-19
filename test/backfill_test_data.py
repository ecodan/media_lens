#!/usr/bin/env python3
"""
Backfill script to generate 14 days of minimal test data for testing purposes.
Creates realistic job directory structure with minimal content to keep file sizes low.
"""

import datetime
import json
import random
from pathlib import Path
from typing import Any, Dict, List

# Minimal article templates
ARTICLE_TEMPLATES = [
    {
        "title": "Breaking: Tech Giant Announces New {product}",
        "text": "A major technology company revealed its latest {product} today. The announcement comes amid growing market competition.\nExperts say this development could reshape the industry landscape.",
    },
    {
        "title": "Global Markets React to {event}",
        "text": "Financial markets showed mixed reactions following {event}. Trading volumes increased significantly.\nAnalysts predict continued volatility in the coming weeks.",
    },
    {
        "title": "Climate Summit Addresses {topic}",
        "text": "World leaders gathered to discuss {topic} at the international climate summit. New initiatives were proposed.\nThe summit continues for three more days with additional sessions planned.",
    },
    {
        "title": "Sports Update: {team} Wins Championship",
        "text": "In a thrilling match, {team} secured victory in the championship finals. Fans celebrated across the city.\nThe victory marks their first championship win in over a decade.",
    },
    {
        "title": "Medical Research: New Study on {topic}",
        "text": "Researchers published findings on {topic} in a peer-reviewed journal. The study involved thousands of participants.\nResults suggest promising applications for future treatments.",
    },
]

SITES = ["www.bbc.com", "www.cnn.com", "www.foxnews.com", "www.reuters.com"]

PRODUCT_WORDS = [
    "smartphone",
    "AI assistant",
    "electric vehicle",
    "streaming service",
    "cloud platform",
]
EVENT_WORDS = [
    "policy changes",
    "merger announcement",
    "earnings report",
    "regulatory decision",
    "trade agreement",
]
TOPIC_WORDS = [
    "renewable energy",
    "carbon emissions",
    "ocean conservation",
    "sustainable agriculture",
    "green technology",
]
TEAM_WORDS = ["Lions", "Eagles", "Panthers", "Tigers", "Bears"]


def generate_minimal_article(template_idx: int, site: str) -> Dict[str, Any]:
    """Generate a minimal article with realistic content."""
    template = ARTICLE_TEMPLATES[template_idx]

    # Replace placeholders with random words
    replacements = {
        "product": random.choice(PRODUCT_WORDS),
        "event": random.choice(EVENT_WORDS),
        "topic": random.choice(TOPIC_WORDS),
        "team": random.choice(TEAM_WORDS),
    }

    title = template["title"]
    text = template["text"]

    for key, value in replacements.items():
        title = title.replace(f"{{{key}}}", value)
        text = text.replace(f"{{{key}}}", value)

    # Add site-specific suffix to title
    site_suffix = site.replace("www.", "").replace(".com", "").upper()
    title = f"{title} | {site_suffix}"

    return {"title": title, "text": text, "error": None}


def generate_extracted_json(
    articles: List[Dict[str, Any]], job_timestamp: str, site: str
) -> Dict[str, Any]:
    """Generate the extracted.json file with story metadata."""
    stories = []

    for i, article in enumerate(articles):
        # Create realistic URLs
        url_suffix = article["title"].lower().replace(" ", "-").replace(":", "")[:30]
        url = f"/{random.choice(['news', 'articles', 'stories'])}/{url_suffix}-{random.randint(1000, 9999)}"

        stories.append(
            {
                "title": article["title"].split(" | ")[0],  # Remove site suffix
                "date": "",
                "url": url,
                "article_text": f"/Users/dan/dev/code/projects/python/media_lens/working/out/{job_timestamp}/{site}-clean-article-{i}.json",
            }
        )

    return {"stories": stories}


def create_job_directory(base_path: Path, date: datetime.date, time_str: str) -> Path:
    """Create job directory structure."""
    job_path = base_path / str(date.year) / f"{date.month:02d}" / f"{date.day:02d}" / time_str
    job_path.mkdir(parents=True, exist_ok=True)
    return job_path


def backfill_test_data(days_back: int = 14):
    """Generate test data for the specified number of days back."""
    base_path = Path("../working/out/jobs")
    base_path.mkdir(parents=True, exist_ok=True)

    today = datetime.date.today()

    print(f"Generating {days_back} days of test data...")

    for day_offset in range(days_back):
        target_date = today - datetime.timedelta(days=day_offset)

        # Generate 1-2 jobs per day at different times
        num_jobs = random.randint(1, 2)

        for _job_idx in range(num_jobs):
            # Generate realistic timestamps
            hour = random.randint(6, 22)  # Between 6 AM and 10 PM
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            time_str = f"{hour:02d}{minute:02d}{second:02d}"

            job_path = create_job_directory(base_path, target_date, time_str)
            job_timestamp = f"{target_date.isoformat()}T{hour:02d}:{minute:02d}:{second:02d}+00:00"

            print(f"  Creating job: {target_date} {time_str}")

            # Generate data for each site
            for site in SITES:
                # Generate 2-4 articles per site
                num_articles = random.randint(2, 4)
                articles = []

                # Use different templates for variety
                template_indices = random.sample(
                    range(len(ARTICLE_TEMPLATES)), min(num_articles, len(ARTICLE_TEMPLATES))
                )

                for i, template_idx in enumerate(template_indices):
                    article = generate_minimal_article(template_idx, site)
                    articles.append(article)

                    # Save individual article file
                    article_file = job_path / f"{site}-clean-article-{i}.json"
                    with open(article_file, "w") as f:
                        json.dump(article, f, indent=2)

                # Generate extracted.json for this site
                extracted_data = generate_extracted_json(articles, job_timestamp, site)
                extracted_file = job_path / f"{site}-clean-extracted.json"
                with open(extracted_file, "w") as f:
                    json.dump(extracted_data, f, indent=2)

                # Create a minimal clean.html file (empty but present)
                html_file = job_path / f"{site}-clean.html"
                with open(html_file, "w") as f:
                    f.write(
                        f"<html><head><title>Clean data for {site}</title></head><body><!-- Minimal HTML placeholder --></body></html>"
                    )

    print(f"\nBackfill complete! Generated test data for {days_back} days.")
    print(f"Data created in: {base_path.absolute()}")

    # Show summary
    total_jobs = len(list(base_path.rglob("*-clean-extracted.json"))) // len(SITES)
    total_articles = len(list(base_path.rglob("*-clean-article-*.json")))
    print(f"Summary: {total_jobs} jobs, {total_articles} articles across {len(SITES)} sites")


if __name__ == "__main__":
    backfill_test_data(14)
