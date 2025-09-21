import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from anthropic import APIError

from src.media_lens.extraction.interpreter import LLMWebsiteInterpreter


def test_interpret_from_files(temp_dir, mock_llm_agent, test_storage_adapter):
    """Test interpret_from_files method with sample files."""
    # Create test interpreter with mock agent
    interpreter = LLMWebsiteInterpreter(agent=mock_llm_agent, storage=test_storage_adapter)
    
    # Create test files using storage adapter
    storage = test_storage_adapter
    file_paths = []
    for i in range(3):
        file_path = f"test-article-{i}.json"
        storage.write_json(file_path, {
            "title": f"Test Article {i}",
            "text": f"This is the content of article {i}."
        })
        file_paths.append(f"{temp_dir}/{file_path}")
    
    # Call interpret_from_files
    result = interpreter.interpret_files(file_paths)
    
    # Verify results
    assert isinstance(result, list)
    assert len(result) > 0
    assert "question" in result[0]
    assert "answer" in result[0]


def test_interpret(mock_llm_agent, test_storage_adapter):
    """Test interpret method with sample content."""
    # Create test interpreter with mock agent and storage adapter
    interpreter = LLMWebsiteInterpreter(agent=mock_llm_agent, storage=test_storage_adapter)
    
    # Create test content
    content = [
        {
            "title": "Test Article 1",
            "text": "This is the content of article 1."
        },
        {
            "title": "Test Article 2",
            "text": "This is the content of article 2."
        }
    ]
    
    # Call interpret
    result = interpreter.interpret(content)
    
    # Verify results
    assert isinstance(result, list)
    assert len(result) > 0
    assert "question" in result[0]
    assert "answer" in result[0]


@patch('src.media_lens.extraction.interpreter.json.loads')
def test_interpret_with_json_error(mock_json_loads, mock_llm_agent, test_storage_adapter):
    """Test error handling when JSON parsing fails."""
    # Make json.loads raise an exception
    mock_json_loads.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
    
    # Create test interpreter with mock agent and storage adapter
    interpreter = LLMWebsiteInterpreter(agent=mock_llm_agent, storage=test_storage_adapter)
    
    # Create test content
    content = [
        {
            "title": "Test Article 1",
            "text": "This is the content of article 1."
        }
    ]
    
    # Call interpret
    result = interpreter.interpret(content)
    
    # Verify error handling
    assert result == []


def test_interpret_weeks_content(mock_llm_agent, temp_dir, test_storage_adapter):
    """Test interpret_site_content method."""
    # Create test interpreter with mock agent and storage adapter
    interpreter = LLMWebsiteInterpreter(agent=mock_llm_agent, storage=test_storage_adapter)
    
    # Create test content structure for a single site
    site = "www.test1.com"
    content = [
        [
            {"title": "Test1 Article 1", "text": "Content 1", "url": "/article1"},
            {"title": "Test1 Article 2", "text": "Content 2", "url": "/article2"}
        ],
        [
            {"title": "Test1 Article 3", "text": "Content 3", "url": "/article3"},
            {"title": "Test1 Article 4", "text": "Content 4", "url": "/article4"}
        ]
    ]
    
    # Call interpret_site_content with correct arguments
    result = interpreter.interpret_site_content(site, content)
    
    # Verify results
    assert isinstance(result, list)
    assert len(result) > 0
    assert "site" in result[0]
    assert "question" in result[0]
    assert "answer" in result[0]


def test_interpret_weeks_content_error_handling(mock_llm_agent, test_storage_adapter):
    """Test error handling in interpret_site_content."""
    # Create test interpreter with mock agent and storage adapter
    interpreter = LLMWebsiteInterpreter(agent=mock_llm_agent, storage=test_storage_adapter)
    
    # Create invalid content structure
    site = "www.test1.com"
    invalid_content = "not-a-list"  # Invalid type
    
    # Call interpret_site_content
    result = interpreter.interpret_site_content(site, invalid_content)
    
    # Verify error handling
    assert isinstance(result, list)
    assert len(result) > 0
    assert "question" in result[0]  # Should return fallback content