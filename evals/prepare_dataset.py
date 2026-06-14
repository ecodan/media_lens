"""
Dataset preparation for model-upgrade-eval gavel-ai evaluation harness.

Samples golden data from working/gcs and produces three scenarios.json files:
- headline-extraction-scenarios.json
- interpretation-scenarios.json
- daily-summary-scenarios.json

Scenarios follow the gavel-ai format: {id, input, expected_behavior, expected_output}
"""

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configuration
GOLDEN_ROOT = Path(__file__).parent.parent / "working" / "gcs"
OUTPUT_DIR = Path(__file__).parent / "data"
SITES = ["www.bbc.com", "www.cnn.com", "www.foxnews.com"]

HEADLINE_TARGET = 25
INTERPRETATION_TARGET = 25
SUMMARY_TARGET = 25

# HTML truncation matching production code
MAX_HTML_TOKENS = 100000
CHARS_PER_TOKEN = 4  # rough estimate


def truncate_html(html: str, max_tokens: int = MAX_HTML_TOKENS) -> str:
    """Truncate HTML to approximately max_tokens."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    if len(html) <= max_chars:
        return html
    return html[:max_chars]


def prepare_headline_scenarios(target_n: int = HEADLINE_TARGET) -> List[Dict[str, Any]]:
    """
    Prepare headline extraction scenarios from jobs/YYYY/MM/DD/HHmmss/ directories.
    Each scenario has a cleaned HTML input and golden extracted JSON reference.
    """
    scenarios: List[Dict[str, Any]] = []
    job_dirs: List[Path] = []

    # Collect all job dirs
    for job_dir in sorted((GOLDEN_ROOT / "jobs").rglob("*")):
        if not job_dir.is_dir() or job_dir.name in ["jobs", "2025", "2026"]:
            continue
        # Check if it has the pattern jobs/YYYY/MM/DD/HHmmss
        if len(job_dir.parts) >= 5 and job_dir.parts[-5] == "jobs":
            job_dirs.append(job_dir)

    # Sample evenly across sites and dates
    job_dirs = sorted(job_dirs)
    if len(job_dirs) > target_n * 3:
        step = len(job_dirs) // (target_n * 3)
        sampled = job_dirs[::step][:target_n * 3]
    else:
        sampled = job_dirs

    for job_dir in sampled:
        for site in SITES:
            html_file = job_dir / f"{site}.html"
            # Try both the clean version and raw version
            if not html_file.exists():
                clean_html_file = job_dir / f"{site}-clean.html"
                if clean_html_file.exists():
                    html_file = clean_html_file
                else:
                    continue

            extracted_file = job_dir / f"{site}-clean-extracted.json"
            if not extracted_file.exists():
                continue

            try:
                with open(html_file) as f:
                    html_content = f.read()
                with open(extracted_file) as f:
                    golden_extracted = json.load(f)

                # Truncate HTML
                html_content = truncate_html(html_content)

                timestamp = job_dir.name
                scenario: Dict[str, Any] = {
                    "id": f"headline-{timestamp}-{site.replace('.', '-')}",
                    "input": {
                        "site": site,
                        "html": html_content,
                    },
                    "expected_behavior": "Extract 3-8 prominent headlines verbatim from the HTML with correct URLs. Return valid JSON with {\"stories\": [{\"title\": \"...\", \"date\": \"...\", \"url\": \"...\"}]}",
                    "expected_output": golden_extracted,
                }
                scenarios.append(scenario)

                if len(scenarios) >= target_n:
                    break
            except (json.JSONDecodeError, IOError) as e:
                print(f"Skipping {html_file}: {e}")
                continue

        if len(scenarios) >= target_n:
            break

    print(f"Prepared {len(scenarios)} headline extraction scenarios")
    return scenarios[:target_n]


def prepare_interpretation_scenarios(target_n: int = INTERPRETATION_TARGET) -> List[Dict[str, Any]]:
    """
    Prepare interpretation scenarios from jobs/YYYY/MM/DD/HHmmss/ directories.
    Input: concatenated article texts.
    Golden reference: interpreted JSON (when available).
    """
    scenarios: List[Dict[str, Any]] = []
    job_dirs: List[Path] = []

    # Collect all job dirs
    for job_dir in sorted((GOLDEN_ROOT / "jobs").rglob("*")):
        if not job_dir.is_dir() or job_dir.name in ["jobs", "2025", "2026"]:
            continue
        if len(job_dir.parts) >= 5 and job_dir.parts[-5] == "jobs":
            job_dirs.append(job_dir)

    # Sample evenly
    job_dirs = sorted(job_dirs)
    if len(job_dirs) > target_n * 2:
        step = len(job_dirs) // (target_n * 2)
        sampled = job_dirs[::step][: target_n * 2]
    else:
        sampled = job_dirs

    for job_dir in sampled:
        # Check if this job dir has articles and (optionally) an interpreted output
        article_files: List[Path] = list(job_dir.glob("*-clean-article-*.json"))
        if not article_files:
            continue

        # Collect article texts
        articles_text: List[str] = []
        for article_file in sorted(article_files):
            try:
                with open(article_file) as f:
                    article = json.load(f)
                    if "text" in article:
                        articles_text.append(article["text"])
            except (json.JSONDecodeError, IOError):
                pass

        if not articles_text:
            continue

        # Concatenate articles
        content = "\n\n---\n\n".join(articles_text)
        if len(content) > 80000:
            content = content[:80000]

        # Try to find golden reference (can be in jobs/ or intermediate/)
        golden_ref: Optional[Dict[str, Any]] = None
        timestamp = job_dir.name

        # Check jobs dir first (older format stores interpreted files directly)
        for site in SITES:
            interpreted_file = job_dir / f"{site}-interpreted.json"
            if interpreted_file.exists():
                try:
                    with open(interpreted_file) as f:
                        golden_ref = json.load(f)
                        break
                except json.JSONDecodeError:
                    pass

        # Check intermediate dir (newer format)
        if golden_ref is None:
            intermediate_dir = GOLDEN_ROOT / "intermediate" / timestamp
            if intermediate_dir.exists():
                for site in SITES:
                    interpreted_file = intermediate_dir / f"{site}-interpreted.json"
                    if interpreted_file.exists():
                        try:
                            with open(interpreted_file) as f:
                                golden_ref = json.load(f)
                                break
                        except json.JSONDecodeError:
                            pass

        scenario: Dict[str, Any] = {
            "id": f"interp-{timestamp}",
            "input": {
                "content": content,
            },
            "expected_behavior": "Return exactly 5 Q&A JSON objects with structure [{\"question\": \"...\", \"answer\": \"...\"}]",
            "expected_output": golden_ref,
        }
        scenarios.append(scenario)

        if len(scenarios) >= target_n:
            break

    print(f"Prepared {len(scenarios)} interpretation scenarios ({sum(1 for s in scenarios if s['expected_output'] is not None)} with expected outputs)")
    return scenarios[:target_n]


def prepare_summary_scenarios(target_n: int = SUMMARY_TARGET) -> List[Dict[str, Any]]:
    """
    Prepare daily summary scenarios from jobs/YYYY/MM/DD/HHmmss/daily_news.txt.
    Input: concatenated articles for the day.
    Golden reference: the daily_news.txt content.
    """
    scenarios: List[Dict[str, Any]] = []
    summary_files: List[Path] = list((GOLDEN_ROOT / "jobs").rglob("daily_news.txt"))

    # Sample evenly
    if len(summary_files) > target_n * 2:
        summary_files = random.sample(summary_files, target_n * 2)

    for summary_file in sorted(summary_files):
        job_dir = summary_file.parent

        # Collect articles for this job
        article_files: List[Path] = list(job_dir.glob("*-clean-article-*.json"))
        if not article_files:
            continue

        articles_text: List[str] = []
        for article_file in sorted(article_files):
            try:
                with open(article_file) as f:
                    article = json.load(f)
                    if "text" in article:
                        articles_text.append(article["text"])
            except (json.JSONDecodeError, IOError):
                pass

        if not articles_text:
            continue

        # Concatenate articles
        content = "\n\n---\n\n".join(articles_text)
        if len(content) > 100000:
            content = content[:100000]

        # Read golden summary
        try:
            with open(summary_file) as f:
                golden_summary = f.read()
        except IOError:
            continue

        timestamp = job_dir.name
        scenario: Dict[str, Any] = {
            "id": f"summary-{timestamp}",
            "input": {
                "content": content,
            },
            "expected_behavior": "Return a coherent prose summary of the day's news (100-500 words), not bullet points.",
            "expected_output": golden_summary,
        }
        scenarios.append(scenario)

        if len(scenarios) >= target_n:
            break

    print(f"Prepared {len(scenarios)} daily summary scenarios")
    return scenarios[:target_n]


def main():
    """Run all scenario preparations and write output files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Using golden data root: {GOLDEN_ROOT}")
    print()

    # Prepare headline extraction
    headline_scenarios = prepare_headline_scenarios(HEADLINE_TARGET)
    headline_output = OUTPUT_DIR / "headline-extraction-scenarios.json"
    with open(headline_output, "w") as f:
        json.dump({"scenarios": headline_scenarios}, f, indent=2)
    print(f"Wrote {headline_output}")

    # Prepare interpretation
    interpretation_scenarios = prepare_interpretation_scenarios(INTERPRETATION_TARGET)
    interpretation_output = OUTPUT_DIR / "interpretation-scenarios.json"
    with open(interpretation_output, "w") as f:
        json.dump({"scenarios": interpretation_scenarios}, f, indent=2)
    print(f"Wrote {interpretation_output}")

    # Prepare summary
    summary_scenarios = prepare_summary_scenarios(SUMMARY_TARGET)
    summary_output = OUTPUT_DIR / "daily-summary-scenarios.json"
    with open(summary_output, "w") as f:
        json.dump({"scenarios": summary_scenarios}, f, indent=2)
    print(f"Wrote {summary_output}")

    print()
    print("✓ All scenario files prepared")
    print(f"  - {len(headline_scenarios)} headline scenarios")
    print(f"  - {len(interpretation_scenarios)} interpretation scenarios")
    print(f"  - {len(summary_scenarios)} summary scenarios")


if __name__ == "__main__":
    main()
