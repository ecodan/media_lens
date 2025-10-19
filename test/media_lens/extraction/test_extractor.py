from unittest.mock import MagicMock, patch

import pytest

from src.media_lens.extraction.agent import Agent
from src.media_lens.extraction.exceptions import ArticleExtractionError
from src.media_lens.extraction.extractor import ContextExtractor


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    agent = MagicMock(spec=Agent)
    return agent


@pytest.fixture
def mock_storage():
    """Create a mock storage adapter."""
    storage = MagicMock()
    return storage


@pytest.fixture
def extractor(mock_agent, mock_storage):
    """Create a context extractor with mocked dependencies."""
    with patch("src.media_lens.extraction.extractor.shared_storage", mock_storage):
        extractor = ContextExtractor(agent=mock_agent, working_dir="test_dir")
        return extractor


def test_process_relative_url_with_absolute_url():
    """Test processing URL that already has protocol."""
    result = ContextExtractor._process_relative_url(
        "https://www.cnn.com/article", "www.cnn.com-extracted.json"
    )
    assert result == "https://www.cnn.com/article"


def test_process_relative_url_with_relative_url():
    """Test processing relative URL."""
    result = ContextExtractor._process_relative_url(
        "/politics/article-1", "www.cnn.com-extracted.json"
    )
    assert result == "https://www.cnn.com/politics/article-1"


def test_process_relative_url_without_leading_slash():
    """Test processing relative URL without leading slash."""
    result = ContextExtractor._process_relative_url(
        "politics/article-1", "www.cnn.com-extracted.json"
    )
    assert result == "https://www.cnn.com/politics/article-1"


def test_process_relative_url_invalid_filename():
    """Test processing URL with invalid filename format."""
    with pytest.raises(ValueError, match="Cannot extract domain from filename"):
        ContextExtractor._process_relative_url("/article", "invalid-filename.json")


def test_validate_extractions_success(extractor, mock_storage):
    """Test validation passes when all sites have 5+ articles."""
    # Mock storage to return extracted files with sufficient articles
    mock_storage.get_files_by_pattern.return_value = [
        "test_dir/www.cnn.com-clean-extracted.json",
        "test_dir/www.bbc.com-clean-extracted.json",
    ]

    # Mock read_json to return data with 5+ stories
    mock_storage.read_json.side_effect = [
        {"stories": [{"title": f"Story {i}"} for i in range(5)]},  # CNN: 5 stories
        {"stories": [{"title": f"Story {i}"} for i in range(7)]},  # BBC: 7 stories
    ]

    # Validation should pass without exception
    extractor._validate_extractions("test_dir")


def test_validate_extractions_failure_single_site(extractor, mock_storage):
    """Test validation fails when one site has <5 articles."""
    # Mock storage to return extracted files
    mock_storage.get_files_by_pattern.return_value = ["test_dir/www.cnn.com-clean-extracted.json"]

    # Mock read_json to return insufficient stories
    mock_storage.read_json.return_value = {
        "stories": [{"title": f"Story {i}"} for i in range(3)]  # Only 3 stories
    }

    # Validation should raise ArticleExtractionError
    with pytest.raises(ArticleExtractionError) as exc_info:
        extractor._validate_extractions("test_dir")

    error = exc_info.value
    assert error.site == "multiple"
    assert "www.cnn.com" in str(error)
    assert "extracted 3/5 articles" in str(error)


def test_validate_extractions_failure_multiple_sites(extractor, mock_storage):
    """Test validation fails when multiple sites have <5 articles."""
    # Mock storage to return multiple extracted files
    mock_storage.get_files_by_pattern.return_value = [
        "test_dir/www.cnn.com-clean-extracted.json",
        "test_dir/www.bbc.com-clean-extracted.json",
        "test_dir/www.foxnews.com-clean-extracted.json",
    ]

    # Mock read_json to return mixed results
    mock_storage.read_json.side_effect = [
        {"stories": [{"title": f"Story {i}"} for i in range(2)]},  # CNN: 2 stories (fail)
        {"stories": [{"title": f"Story {i}"} for i in range(6)]},  # BBC: 6 stories (pass)
        {"stories": [{"title": f"Story {i}"} for i in range(1)]},  # Fox: 1 story (fail)
    ]

    # Validation should raise ArticleExtractionError with all failures
    with pytest.raises(ArticleExtractionError) as exc_info:
        extractor._validate_extractions("test_dir")

    error = exc_info.value
    error_str = str(error)
    assert "www.cnn.com" in error_str
    assert "www.foxnews.com" in error_str
    assert "www.bbc.com" not in error_str  # BBC passed, should not be in error


def test_validate_extractions_empty_stories(extractor, mock_storage):
    """Test validation fails when stories array is empty."""
    # Mock storage
    mock_storage.get_files_by_pattern.return_value = ["test_dir/www.cnn.com-clean-extracted.json"]

    # Mock read_json to return empty stories
    mock_storage.read_json.return_value = {"stories": []}

    # Validation should raise error
    with pytest.raises(ArticleExtractionError) as exc_info:
        extractor._validate_extractions("test_dir")

    assert "extracted 0/5 articles" in str(exc_info.value)


def test_validate_extractions_missing_stories_key(extractor, mock_storage):
    """Test validation handles missing 'stories' key gracefully."""
    # Mock storage
    mock_storage.get_files_by_pattern.return_value = ["test_dir/www.cnn.com-clean-extracted.json"]

    # Mock read_json to return data without 'stories' key
    mock_storage.read_json.return_value = {"error": "extraction failed"}

    # Validation should raise error (treats missing key as 0 stories)
    with pytest.raises(ArticleExtractionError) as exc_info:
        extractor._validate_extractions("test_dir")

    assert "extracted 0/5 articles" in str(exc_info.value)


def test_validate_extractions_invalid_filename(extractor, mock_storage):
    """Test validation skips files with invalid filenames."""
    # Mock storage with one valid and one invalid filename
    mock_storage.get_files_by_pattern.return_value = [
        "test_dir/www.cnn.com-clean-extracted.json",
        "test_dir/invalid-name.json",  # No domain pattern
    ]

    # Mock read_json for valid file only
    mock_storage.read_json.return_value = {"stories": [{"title": f"Story {i}"} for i in range(5)]}

    # Validation should pass (invalid file is skipped, valid file has enough stories)
    extractor._validate_extractions("test_dir")

    # Verify read_json was only called once (for valid file)
    assert mock_storage.read_json.call_count == 1


def test_validate_extractions_exactly_five_stories(extractor, mock_storage):
    """Test validation passes with exactly 5 stories (boundary test)."""
    # Mock storage
    mock_storage.get_files_by_pattern.return_value = ["test_dir/www.cnn.com-clean-extracted.json"]

    # Mock read_json with exactly 5 stories
    mock_storage.read_json.return_value = {"stories": [{"title": f"Story {i}"} for i in range(5)]}

    # Validation should pass
    extractor._validate_extractions("test_dir")


def test_validate_extractions_four_stories(extractor, mock_storage):
    """Test validation fails with 4 stories (boundary test)."""
    # Mock storage
    mock_storage.get_files_by_pattern.return_value = ["test_dir/www.cnn.com-clean-extracted.json"]

    # Mock read_json with exactly 4 stories
    mock_storage.read_json.return_value = {"stories": [{"title": f"Story {i}"} for i in range(4)]}

    # Validation should fail
    with pytest.raises(ArticleExtractionError):
        extractor._validate_extractions("test_dir")


@pytest.mark.asyncio
async def test_run_calls_validation(extractor, mock_storage, mock_agent):
    """Test that run() calls validation after extraction."""
    # Mock storage methods
    mock_storage.get_files_by_pattern.side_effect = [
        ["test_dir/www.cnn.com-clean.html"],  # First call: get HTML files
        ["test_dir/www.cnn.com-clean-extracted.json"],  # Second call: validation
    ]
    mock_storage.read_text.return_value = "<html>Test</html>"
    mock_storage.read_json.return_value = {"stories": [{"title": f"Story {i}"} for i in range(5)]}

    # Mock headline extractor
    with patch.object(extractor.headline_extractor, "extract") as mock_extract:
        mock_extract.return_value = {
            "stories": [{"title": "News 1", "url": "https://example.com/1"}]
        }

        # Mock article collector
        with patch.object(extractor.article_collector, "extract_article") as mock_article:
            mock_article.return_value = {"text": "Article content"}

            # Run extraction
            await extractor.run(delay_between_sites_secs=0)

    # Verify validation was called (via second get_files_by_pattern call)
    assert mock_storage.get_files_by_pattern.call_count == 2


@pytest.mark.asyncio
async def test_run_validation_failure_raises_exception(extractor, mock_storage, mock_agent):
    """Test that validation failure raises ArticleExtractionError during run."""
    # Mock storage methods
    mock_storage.get_files_by_pattern.side_effect = [
        ["test_dir/www.cnn.com-clean.html"],  # HTML files
        ["test_dir/www.cnn.com-clean-extracted.json"],  # Validation files
    ]
    mock_storage.read_text.return_value = "<html>Test</html>"

    # Mock insufficient stories for validation
    mock_storage.read_json.return_value = {
        "stories": [{"title": f"Story {i}"} for i in range(2)]  # Only 2 stories
    }

    # Mock headline extractor
    with patch.object(extractor.headline_extractor, "extract") as mock_extract:
        mock_extract.return_value = {"stories": [{"title": "News 1"}]}

        # Run should raise ArticleExtractionError
        with pytest.raises(ArticleExtractionError):
            await extractor.run(delay_between_sites_secs=0)
