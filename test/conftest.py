import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict

import pytest

from src.media_lens.common import utc_timestamp
from src.media_lens.storage_adapter import StorageAdapter


@pytest.fixture
def temp_dir():
    """Create a temporary directory that is cleaned up after the test."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_html_content():
    """Sample HTML content for testing scrapers and cleaners."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test News Site</title>
    </head>
    <body>
        <div class="main-content">
            <div class="headline">
                <h1><a href="/test-article-1">Breaking News: Test Headline 1</a></h1>
                <p>This is a test summary for the first article.</p>
            </div>
            <div class="headline">
                <h1><a href="/test-article-2">Breaking News: Test Headline 2</a></h1>
                <p>This is a test summary for the second article.</p>
            </div>
            <div class="article-content">
                <p>This is paragraph 1 of the article content.</p>
                <p>This is paragraph 2 of the article content.</p>
                <p>This is paragraph 3 of the article content.</p>
            </div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_article_json():
    """Sample article data in JSON format."""
    return {
        "title": "Breaking News: Test Headline",
        "text": "This is paragraph 1 of the article content.\n\nThis is paragraph 2 of the article content.",
        "url": "/test-article-1"
    }


@pytest.fixture
def test_storage_adapter(monkeypatch, temp_dir):
    """Create a storage adapter instance for testing."""
    # Set environment for local testing
    monkeypatch.setenv("USE_CLOUD_STORAGE", "false")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(temp_dir))
    
    return StorageAdapter()

@pytest.fixture
def sample_job_directory(temp_dir, test_storage_adapter):
    """Create a sample job directory with test data files using the storage adapter."""
    # Create job directory with timestamp name in the backwards-compatible format
    # Use a fixed timestamp for testing to ensure consistent week key generation
    fixed_timestamp = "2025-02-26_153000"  # Format: YYYY-MM-DD_HHMMSS
    job_dir = temp_dir / fixed_timestamp
    job_dir.mkdir(exist_ok=True)
    
    storage = test_storage_adapter
    
    # Sample site data
    sites = ["www.test1.com", "www.test2.com"]
    
    # Create sample files for each site
    for site in sites:
        # Create HTML file
        storage.write_text(f"{fixed_timestamp}/{site}.html", "<html><body>Test content</body></html>")
        
        # Create cleaned HTML file
        storage.write_text(f"{fixed_timestamp}/{site}-clean.html", "<html><body>Cleaned content</body></html>")
        
        # Create articles
        for i in range(3):
            article = {
                "title": f"Test Article {i+1} for {site}",
                "text": f"This is the content of article {i+1} for {site}.",
                "url": f"/{site}/article-{i+1}"
            }
            
            storage.write_json(f"{fixed_timestamp}/{site}-clean-article-{i}.json", article)
        
        # Create extracted data
        extracted = {
            "stories": [
                {
                    "title": f"Test Article 1 for {site}",
                    "summary": f"Summary for article 1 from {site}",
                    "url": f"/{site}/article-1"
                },
                {
                    "title": f"Test Article 2 for {site}",
                    "summary": f"Summary for article 2 from {site}",
                    "url": f"/{site}/article-2"
                }
            ]
        }
        
        storage.write_json(f"{fixed_timestamp}/{site}-clean-extracted.json", extracted)
        
        # Create interpreted data
        interpreted = [
            {
                "question": "What is the most important news right now?",
                "answer": f"The most important news according to {site} is Test Article 1."
            },
            {
                "question": "What are biggest issues in the world right now?",
                "answer": f"According to {site}, the biggest issues are testing and quality assurance."
            }
        ]
        
        storage.write_json(f"{fixed_timestamp}/{site}-interpreted.json", interpreted)
    
    return job_dir


@pytest.fixture
def mock_llm_agent():
    """Mock LLM agent that returns predefined responses."""
    class MockAgent:
        def invoke(self, system_prompt, user_prompt):
            """Return a mock response."""
            return """
            [
                {
                    "question": "What is the most important news right now?",
                    "answer": "The most important news is about testing."
                },
                {
                    "question": "What are biggest issues in the world right now?",
                    "answer": "The biggest issues are unit testing, integration testing, and system testing."
                }
            ]
            """
    
    return MockAgent()