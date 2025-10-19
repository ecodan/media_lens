import json
from unittest.mock import MagicMock

import pytest

from src.media_lens.extraction.agent import Agent, ResponseFormat
from src.media_lens.extraction.headliner import GATHERING_PROMPT, LLMHeadlineExtractor


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    agent = MagicMock(spec=Agent)
    return agent


@pytest.fixture
def extractor(mock_agent):
    """Create a headline extractor with mocked agent."""
    ext = LLMHeadlineExtractor(agent=mock_agent)
    return ext


def test_extract_with_valid_json(extractor, mock_agent):
    """Test successful extraction with valid JSON response."""
    # Mock LLM responses
    cot_response = "<thinking>Analysis</thinking><output>Headlines found</output>"
    json_response = (
        '{"stories": [{"title": "News 1", "date": "2025-01-01", "url": "https://example.com/1"}]}'
    )

    mock_agent.invoke.side_effect = [cot_response, json_response]

    # Test extraction
    result = extractor.extract("<html>Test content</html>")

    # Verify result
    assert "stories" in result
    assert len(result["stories"]) == 1
    assert result["stories"][0]["title"] == "News 1"

    # Verify agent was called twice (CoT + Gathering)
    assert mock_agent.invoke.call_count == 2


def test_extract_with_json_parsing_error(extractor, mock_agent):
    """Test JSONParsingError handling when LLM returns invalid JSON."""
    # Mock LLM responses - second response is invalid JSON
    cot_response = "<thinking>Analysis</thinking><output>Headlines found</output>"
    invalid_json = '{"stories": [{"title": "News 1"} This is broken JSON'

    mock_agent.invoke.side_effect = [cot_response, invalid_json]

    # Test extraction - should catch JSONParsingError and return error dict
    result = extractor.extract("<html>Test content</html>")

    # Verify error is captured
    assert "error" in result
    assert "JSON parsing failed" in str(result["error"])


def test_extract_with_invalid_json(extractor, mock_agent):
    """Test handling of malformed JSON response."""
    # Mock LLM responses - JSON with syntax errors
    cot_response = "<output>Analysis</output>"
    malformed_json = '{"stories": [{"title": "News 1",}]}'  # Trailing comma

    mock_agent.invoke.side_effect = [cot_response, malformed_json]

    # Test extraction
    result = extractor.extract("<html>Test content</html>")

    # Verify error handling
    assert "error" in result


def test_extract_with_empty_stories(extractor, mock_agent):
    """Test extraction when no stories are found."""
    # Mock LLM responses with empty stories array
    cot_response = "<output>No headlines found</output>"
    json_response = '{"stories": []}'

    mock_agent.invoke.side_effect = [cot_response, json_response]

    # Test extraction
    result = extractor.extract("<html>Empty content</html>")

    # Verify result structure
    assert "stories" in result
    assert len(result["stories"]) == 0


def test_extract_with_agent_exception(extractor, mock_agent):
    """Test handling of agent exceptions."""
    # Mock agent raising an exception
    mock_agent.invoke.side_effect = Exception("API Error")

    # Test extraction
    result = extractor.extract("<html>Test content</html>")

    # Verify error handling - code returns dict with error details
    assert "error" in result
    assert "API Error" in result["error"]


def test_truncate_html_short_content():
    """Test HTML truncation with content under token limit."""
    from src.media_lens.extraction.headliner import HeadlineExtractor

    short_html = "<html><body>Short content</body></html>"
    result = HeadlineExtractor._truncate_html(short_html, max_tokens=1000)

    # Should return original content
    assert result == short_html


def test_truncate_html_long_content():
    """Test HTML truncation with content exceeding token limit."""
    from src.media_lens.extraction.headliner import HeadlineExtractor

    # Create long HTML content
    long_html = " ".join([f"word{i}" for i in range(1000)])
    result = HeadlineExtractor._truncate_html(long_html, max_tokens=100)

    # Should be truncated
    assert len(result) < len(long_html)

    # Should contain first tokens
    assert "word0" in result
    assert "word1" in result


def test_gathering_prompt_format():
    """Verify GATHERING_PROMPT has correct format and no contradictory instructions."""
    # Check prompt doesn't have contradictory XML tags requirement
    assert "<analysis>" not in GATHERING_PROMPT

    # Check it has escaped braces for .format() ({{}} instead of {})
    # This is correct - escaped braces prevent KeyError when using .format()
    assert "{{" in GATHERING_PROMPT
    assert "}}" in GATHERING_PROMPT

    # Check it requires JSON only
    assert "ONLY valid JSON" in GATHERING_PROMPT
    assert "No explanations, comments, or text before/after the JSON" in GATHERING_PROMPT

    # Check structure requirements
    assert '"stories"' in GATHERING_PROMPT
    assert '"title"' in GATHERING_PROMPT
    assert '"date"' in GATHERING_PROMPT
    assert '"url"' in GATHERING_PROMPT

    # Verify the format placeholder is present
    assert "{analysis}" in GATHERING_PROMPT


def test_extract_no_caching(extractor, mock_agent):
    """Test that identical content does NOT use caching (caching was removed)."""
    # Mock LLM responses
    cot_response = "<output>Analysis</output>"
    json_response = '{"stories": [{"title": "News 1"}]}'

    mock_agent.invoke.side_effect = [cot_response, json_response, cot_response, json_response]

    # First extraction
    content = "<html>Test content</html>"
    result1 = extractor.extract(content)

    # Second extraction with same content - should NOT use cache
    result2 = extractor.extract(content)

    # Agent should be called 4 times (2 CoT + 2 Gathering)
    assert mock_agent.invoke.call_count == 4

    # Results should be identical (but agent called twice)
    assert result1 == result2


def test_extract_calls_agent_with_correct_format(extractor, mock_agent):
    """Test that agent is called with correct response formats."""
    # Mock LLM responses
    cot_response = "<output>Analysis</output>"
    json_response = '{"stories": []}'

    mock_agent.invoke.side_effect = [cot_response, json_response]

    # Test extraction
    extractor.extract("<html>Test</html>")

    # Verify call arguments
    calls = mock_agent.invoke.call_args_list

    # First call (CoT) should use TEXT format (default)
    assert calls[0][1].get("response_format", ResponseFormat.TEXT) == ResponseFormat.TEXT

    # Second call (Gathering) should use JSON format
    assert calls[1][1]["response_format"] == ResponseFormat.JSON


def test_extract_with_multiple_stories(extractor, mock_agent):
    """Test extraction with multiple news stories."""
    # Mock LLM responses with 5 stories
    cot_response = "<output>Found 5 headlines</output>"
    json_response = json.dumps(
        {
            "stories": [
                {"title": f"News {i}", "date": "2025-01-01", "url": f"https://example.com/{i}"}
                for i in range(1, 6)
            ]
        }
    )

    mock_agent.invoke.side_effect = [cot_response, json_response]

    # Test extraction
    result = extractor.extract("<html>Content with 5 stories</html>")

    # Verify all stories extracted
    assert "stories" in result
    assert len(result["stories"]) == 5

    # Verify story structure
    for i, story in enumerate(result["stories"], 1):
        assert story["title"] == f"News {i}"
        assert story["url"] == f"https://example.com/{i}"


def test_extract_content_truncation(extractor, mock_agent):
    """Test that large HTML content is truncated before sending to LLM."""
    # Create very large HTML content
    large_content = "<html>" + (" ".join([f"word{i}" for i in range(50000)])) + "</html>"

    # Mock LLM responses
    cot_response = "<output>Analysis</output>"
    json_response = '{"stories": []}'
    mock_agent.invoke.side_effect = [cot_response, json_response]

    # Test extraction
    extractor.extract(large_content)

    # Verify agent was called (content was processed despite size)
    assert mock_agent.invoke.call_count == 2

    # Verify truncation occurred (check call args don't contain full content)
    first_call_args = mock_agent.invoke.call_args_list[0]
    user_prompt = first_call_args[1]["user_prompt"]

    # Content should be truncated (not full 50K words)
    assert len(user_prompt) < len(large_content)
