import json
import os
import re
from pathlib import Path

import pytest

from src.media_lens.presentation.html_formatter import (
    convert_relative_url, generate_html_with_template, organize_runs_by_week,
    generate_weekly_content, generate_index_page, generate_html_from_path
)


def test_convert_relative_url():
    """Test converting relative URLs to absolute URLs."""
    # Test cases for different URL formats
    test_cases = [
        # (input_url, site, expected_output)
        ("/news/article", "www.test.com", "https://www.test.com/news/article"),
        ("news/article", "www.test.com", "https://www.test.com/news/article"),
        ("https://www.test.com/news/article", "www.test.com", "https://www.test.com/news/article"),
        ("http://www.test.com/news/article", "www.test.com", "http://www.test.com/news/article"),
    ]
    
    # Check each test case
    for input_url, site, expected in test_cases:
        result = convert_relative_url(input_url, site)
        assert result == expected


def test_generate_html_with_template(temp_dir):
    """Test HTML generation using a Jinja2 template."""
    # Create a simple template
    template_dir = temp_dir / "templates"
    template_dir.mkdir(exist_ok=True)
    
    with open(template_dir / "test_template.j2", "w") as f:
        f.write("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ title }}</title>
        </head>
        <body>
            <h1>{{ title }}</h1>
            <p>{{ content }}</p>
            <ul>
            {% for item in items %}
                <li>{{ item }}</li>
            {% endfor %}
            </ul>
        </body>
        </html>
        """)
    
    # Test content
    content = {
        "title": "Test Page",
        "content": "This is a test page.",
        "items": ["Item 1", "Item 2", "Item 3"]
    }
    
    # Generate HTML
    html = generate_html_with_template(template_dir, "test_template.j2", content)
    
    # Check results
    assert "<title>Test Page</title>" in html
    assert "<h1>Test Page</h1>" in html
    assert "<p>This is a test page.</p>" in html
    assert "<li>Item 1</li>" in html
    assert "<li>Item 2</li>" in html
    assert "<li>Item 3</li>" in html


def test_organize_runs_by_week(sample_job_directory):
    """Test organizing job runs by calendar week."""
    # Get all directories from the sample job directory
    job_dirs = [sample_job_directory]
    sites = ["www.test1.com", "www.test2.com"]
    
    # Call organize_runs_by_week
    result = organize_runs_by_week(job_dirs, sites)
    
    # Check result structure
    assert "report_timestamp" in result
    assert "weeks" in result
    assert len(result["weeks"]) >= 1
    
    # Check week data
    week = result["weeks"][0]
    assert "week_key" in week
    assert "week_display" in week
    assert "runs" in week
    assert len(week["runs"]) >= 1  # At least one run in the week
    
    # Check run data
    run = week["runs"][0]
    assert "run_timestamp" in run
    assert "extracted" in run


def test_generate_weekly_content(sample_job_directory, temp_dir, test_storage_adapter):
    """Test generating content for weekly reports."""
    # First organize runs by week
    job_dirs = [sample_job_directory]
    sites = ["www.test1.com", "www.test2.com"]
    weeks_data = organize_runs_by_week(job_dirs, sites)
    
    # Get the first week
    week_data = weeks_data["weeks"][0]
    
    # Create a weekly interpretation file using the storage adapter
    storage = test_storage_adapter
    storage.write_text(f"weekly-{week_data['week_key']}-interpreted.json", '[]')
    
    # Call generate_weekly_content
    weekly_content = generate_weekly_content(week_data, sites, temp_dir)
    
    # Check result structure
    assert weekly_content["week_key"] == week_data["week_key"]
    assert weekly_content["week_display"] == week_data["week_display"]
    assert weekly_content["sites"] == sites
    assert "site_content" in weekly_content
    assert "runs" in weekly_content
    # Weekly interpretation is no longer included in weekly content
    assert "interpretation" not in weekly_content


def test_generate_index_page(sample_job_directory, temp_dir, test_storage_adapter):
    """Test generating the index page with the latest weekly summary."""
    # First organize runs by week
    job_dirs = [sample_job_directory]
    sites = ["www.test1.com", "www.test2.com"]
    weeks_data = organize_runs_by_week(job_dirs, sites)
    
    # Create a weekly interpretation file for the latest week
    latest_week = weeks_data["weeks"][0]
    latest_week_key = latest_week["week_key"]
    
    # Create weekly interpretation data
    weekly_data = [
        {
            "question": "Test Question 1?",
            "answer": "Test Answer 1",
            "site": "www.test1.com"
        },
        {
            "question": "Test Question 1?",
            "answer": "Test Answer 1 for site 2",
            "site": "www.test2.com"
        },
        {
            "question": "Test Question 2?",
            "answer": "Test Answer 2",
            "site": "www.test1.com"
        }
    ]
    
    # Write the weekly interpretation file
    storage = test_storage_adapter
    storage.write_text(f"weekly-{latest_week_key}-interpreted.json", json.dumps(weekly_data))
    
    # Create template directory and index template
    template_dir = temp_dir / "templates"
    template_dir.mkdir(exist_ok=True)
    
    index_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Media Lens Report</title>
    </head>
    <body>
        {% if weekly_summary %}
        <div>
            <h2>Weekly Media Analysis</h2>
            <p>{{ weekly_summary_date }}</p>
            {% for row in weekly_summary %}
            <div>{{ row.question }}</div>
            {% endfor %}
        </div>
        {% endif %}
        <ul>
        {% for week in weeks %}
            <li>{{ week.week_display }}</li>
        {% endfor %}
        </ul>
    </body>
    </html>
    """
    storage.write_text("templates/index_template.j2", index_template)
    
    # Call generate_index_page
    html = generate_index_page(weeks_data, template_dir, temp_dir)
    
    # Check that HTML was generated and includes the weekly summary
    assert html is not None
    assert "Weekly Media Analysis" in html
    assert "Test Question 1" in html
    
def test_generate_html_from_path(sample_job_directory, temp_dir, test_storage_adapter):
    """Test the main HTML generation function."""
    # Get the storage adapter from the fixture
    storage = test_storage_adapter
    
    # Create template directory
    template_dir = temp_dir / "templates"
    template_dir.mkdir(exist_ok=True)
    
    # Create index template using the storage adapter
    index_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Media Lens Report</title>
        </head>
        <body>
            <h1>Media Lens Report</h1>
            <p>Generated: {{ report_timestamp }}</p>
            
            {% if weekly_summary and sites %}
            <div>
                <h2>Weekly Media Analysis</h2>
                <p>Analysis for the last seven days ending {{ weekly_summary_date }}</p>
                
                <div>
                    <div>
                        <div>Question</div>
                        {% for site in sites %}
                        <div>{{ site }}</div>
                        {% endfor %}
                    </div>
                    {% for row in weekly_summary %}
                    <div>
                        <div>
                            <b>{{ row.question }}</b>
                        </div>
                        {% for site in sites %}
                        <div>
                            {{ row.answers[site] }}
                        </div>
                        {% endfor %}
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
            
            <ul>
            {% for week in weeks %}
                <li>
                    <a href="medialens-{{ week.week_key }}.html">{{ week.week_display }}</a>
                </li>
            {% endfor %}
            </ul>
        </body>
        </html>
        """
    storage.write_text("templates/index_template.j2", index_template)
    
    # Create weekly template using the storage adapter (without weekly interpretation section)
    weekly_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ week_display }} Report</title>
        </head>
        <body>
            <h1>{{ week_display }} Report</h1>
            {% for site in sites %}
            <h2>{{ site }}</h2>
            <ul>
            {% for article in site_content[site] %}
                <li>{{ article.title }}</li>
            {% endfor %}
            </ul>
            {% endfor %}
        </body>
        </html>
        """
    storage.write_text("templates/weekly_template.j2", weekly_template)
    
    # Create a sample weekly interpretation file to ensure processing works
    week_key = "2025-W09"  # Corresponds to our fixed timestamp
    storage.write_text(f"weekly-{week_key}-interpreted.json", '[]')
    
    # Ensure we can find the job directory content
    timestamp_dir = sample_job_directory.name
    
    # Call generate_html_from_path
    sites = ["www.test1.com", "www.test2.com"]
    html = generate_html_from_path(temp_dir, sites, template_dir)
    
    # Check that HTML was generated
    assert html is not None
    
    # Check if files were created using the storage adapter
    assert storage.file_exists("medialens.html")
    
    # Verify HTML content
    assert "<title>Media Lens Report</title>" in html
    assert "<h1>Media Lens Report</h1>" in html