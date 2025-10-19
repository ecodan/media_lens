import json
from unittest.mock import MagicMock, patch

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
        storage.write_json(
            file_path,
            {"title": f"Test Article {i}", "text": f"This is the content of article {i}."},
        )
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
        {"title": "Test Article 1", "text": "This is the content of article 1."},
        {"title": "Test Article 2", "text": "This is the content of article 2."},
    ]

    # Call interpret
    result = interpreter.interpret(content)

    # Verify results
    assert isinstance(result, list)
    assert len(result) > 0
    assert "question" in result[0]
    assert "answer" in result[0]


@patch("src.media_lens.extraction.interpreter.json.loads")
def test_interpret_with_json_error(mock_json_loads, mock_llm_agent, test_storage_adapter):
    """Test error handling when JSON parsing fails."""
    # Make json.loads raise an exception
    mock_json_loads.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

    # Create test interpreter with mock agent and storage adapter
    interpreter = LLMWebsiteInterpreter(agent=mock_llm_agent, storage=test_storage_adapter)

    # Create test content
    content = [{"title": "Test Article 1", "text": "This is the content of article 1."}]

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
            {"title": "Test1 Article 2", "text": "Content 2", "url": "/article2"},
        ],
        [
            {"title": "Test1 Article 3", "text": "Content 3", "url": "/article3"},
            {"title": "Test1 Article 4", "text": "Content 4", "url": "/article4"},
        ],
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


def test_interpret_weeks_with_specific_weeks(mock_llm_agent, test_storage_adapter, temp_dir):
    """Test interpret_weeks method with specific weeks provided."""
    import datetime
    from unittest.mock import patch

    from src.media_lens.job_dir import JobDir

    # Create test interpreter with mock agent and storage adapter
    interpreter = LLMWebsiteInterpreter(agent=mock_llm_agent, storage=test_storage_adapter)

    # Create real JobDir instances (not mocks) for isinstance checks to work
    with patch.object(JobDir, "list_all") as mock_list_all, patch.object(
        JobDir, "group_by_week"
    ) as mock_group_by_week, patch.object(
        test_storage_adapter, "get_intermediate_directory", return_value="intermediate"
    ), patch.object(test_storage_adapter, "get_files_by_pattern", return_value=[]), patch.object(
        test_storage_adapter, "write_json"
    ):
        # Create mock job directories for testing
        mock_job1 = MagicMock(spec=JobDir)
        mock_job1.storage_path = "jobs/2025/02/17/120000"
        mock_job1.datetime = datetime.datetime(2025, 2, 17, 12, 0, 0, tzinfo=datetime.timezone.utc)

        mock_job2 = MagicMock(spec=JobDir)
        mock_job2.storage_path = "jobs/2025/02/18/120000"
        mock_job2.datetime = datetime.datetime(2025, 2, 18, 12, 0, 0, tzinfo=datetime.timezone.utc)

        # Mock JobDir.list_all to return job directories
        mock_list_all.return_value = [mock_job1, mock_job2]

        # Mock JobDir.group_by_week to return weeks with jobs
        mock_group_by_week.return_value = {"2025-W08": [mock_job1, mock_job2]}

        # Test with specific weeks
        sites = ["www.test1.com", "www.test2.com"]
        specific_weeks = ["2025-W08"]

        result = interpreter.interpret_weeks(
            sites=sites, specific_weeks=specific_weeks, use_rolling_for_current=False
        )

        # Verify results
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["week"] == "2025-W08"
        assert "interpretation" in result[0]
        assert "included_days" in result[0]
        assert "days_count" in result[0]


def test_interpret_weeks_with_rolling_for_current(mock_llm_agent, test_storage_adapter, temp_dir):
    """Test interpret_weeks method with rolling 7-day analysis for current week."""
    import datetime
    from unittest.mock import patch

    from src.media_lens.common import get_week_key
    from src.media_lens.job_dir import JobDir

    # Create test interpreter with mock agent and storage adapter
    interpreter = LLMWebsiteInterpreter(agent=mock_llm_agent, storage=test_storage_adapter)

    # Get current week
    current_datetime = datetime.datetime.now(datetime.timezone.utc)
    current_week = get_week_key(current_datetime)

    # Create real JobDir instances (not mocks) for isinstance checks to work
    with patch.object(JobDir, "list_all") as mock_list_all, patch.object(
        JobDir, "group_by_week"
    ) as mock_group_by_week, patch.object(
        test_storage_adapter, "get_intermediate_directory", return_value="intermediate"
    ), patch.object(test_storage_adapter, "get_files_by_pattern", return_value=[]), patch.object(
        test_storage_adapter, "write_json"
    ):
        # Create mock job directories for testing
        mock_job1 = MagicMock(spec=JobDir)
        mock_job1.storage_path = "jobs/2025/10/01/120000"
        mock_job1.datetime = current_datetime - datetime.timedelta(days=2)

        mock_job2 = MagicMock(spec=JobDir)
        mock_job2.storage_path = "jobs/2025/10/02/120000"
        mock_job2.datetime = current_datetime - datetime.timedelta(days=1)

        # Mock JobDir.list_all to return job directories
        mock_list_all.return_value = [mock_job1, mock_job2]

        # Mock JobDir.group_by_week to return current week with jobs
        mock_group_by_week.return_value = {current_week: [mock_job1, mock_job2]}

        # Test with current week using rolling analysis
        sites = ["www.test1.com"]

        result = interpreter.interpret_weeks(
            sites=sites, specific_weeks=[current_week], use_rolling_for_current=True
        )

        # Verify results
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["week"] == current_week
        assert result[0].get("period_type") == "rolling_7_days"
        assert "interpretation" in result[0]
