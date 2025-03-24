import os
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from src.media_lens.runner import (
    extract, interpret, interpret_weekly, format_and_deploy, Steps, summarize_all
)


@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables for testing."""
    with patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test_api_key",
        "OUTPUT_DIR": "/tmp/media_lens_test"
    }):
        yield


@pytest.mark.asyncio
@patch('src.media_lens.runner.ContextExtractor')
async def test_extract(mock_extractor_class, temp_dir, mock_env_vars):
    """Test extract function."""
    # Mock the extractor
    mock_extractor = AsyncMock()
    mock_extractor_class.return_value = mock_extractor
    
    # Create job directory
    job_dir = temp_dir / "2025-02-26T15:30:00+00:00"
    job_dir.mkdir(exist_ok=True)
    
    # Call extract
    await extract(job_dir)
    
    # Verify extractor was called with correct args
    mock_extractor_class.assert_called_once()
    assert mock_extractor.run.call_count == 1
    
    # Check that the extractor was initialized with the job_dir
    _, kwargs = mock_extractor_class.call_args
    assert kwargs['working_dir'] == job_dir


@pytest.mark.asyncio
@patch('src.media_lens.runner.ClaudeLLMAgent')
@patch('src.media_lens.runner.LLMWebsiteInterpreter')
async def test_interpret(mock_interpreter_class, mock_agent_class, temp_dir, mock_env_vars):
    """Test interpret function."""
    # Mock the interpreter
    mock_interpreter = MagicMock()
    mock_interpreter.interpret_from_files.return_value = [
        {"question": "Test Question", "answer": "Test Answer"}
    ]
    mock_interpreter_class.return_value = mock_interpreter
    
    # Create job directory and test files
    job_dir = temp_dir / "2025-02-26T15:30:00+00:00"
    job_dir.mkdir(exist_ok=True)
    
    sites = ["www.test1.com", "www.test2.com"]
    for site in sites:
        # Create article files
        for i in range(3):
            article_path = job_dir / f"{site}-clean-article-{i}.json"
            with open(article_path, "w") as f:
                f.write('{"title": "Test Article", "text": "Test content"}')
    
    # Call interpret
    await interpret(job_dir, sites)
    
    # Verify results
    for site in sites:
        # Check that interpreted file was created
        interpreted_path = job_dir / f"{site}-interpreted.json"
        assert interpreted_path.exists()
        
        # Verify the interpreter was called once per site
        assert mock_interpreter.interpret_from_files.call_count == len(sites)


@pytest.mark.asyncio
@patch('src.media_lens.runner.ClaudeLLMAgent')
@patch('src.media_lens.runner.LLMWebsiteInterpreter')
async def test_interpret_weekly(mock_interpreter_class, mock_agent_class, temp_dir, mock_env_vars):
    """Test weekly interpretation function."""
    # Mock the interpreter
    mock_interpreter = MagicMock()
    mock_interpreter.interpret_weekly.return_value = [
        {
            'week': '2025-W08',
            'file_path': temp_dir / 'weekly-2025-W08-interpreted.json',
            'interpretation': [{"question": "Weekly Question", "answer": "Weekly Answer", "site": "www.test1.com"}]
        }
    ]
    mock_interpreter_class.return_value = mock_interpreter
    
    # Create job root directory
    jobs_root = temp_dir
    
    # Call interpret_weekly with default parameters (current week only)
    sites = ["www.test1.com", "www.test2.com"]
    await interpret_weekly(jobs_root, sites)
    
    # Verify the interpreter was called with correct parameters
    mock_interpreter.interpret_weekly.assert_called_once_with(
        job_dirs_root=jobs_root, 
        sites=sites,
        current_week_only=True,
        overwrite=False,
        specific_weeks=None
    )
    
    # Check that weekly files were created
    assert (temp_dir / 'weekly-2025-W08-interpreted.json').exists()


@pytest.mark.asyncio
@patch('src.media_lens.runner.ClaudeLLMAgent')
@patch('src.media_lens.runner.LLMWebsiteInterpreter')
async def test_interpret_weekly_with_specific_weeks(mock_interpreter_class, mock_agent_class, temp_dir, mock_env_vars):
    """Test weekly interpretation function with specific weeks."""
    # Mock the interpreter
    mock_interpreter = MagicMock()
    mock_interpreter.interpret_weekly.return_value = [
        {
            'week': '2025-W07',
            'file_path': temp_dir / 'weekly-2025-W07-interpreted.json',
            'interpretation': [{"question": "Week 7 Question", "answer": "Week 7 Answer", "site": "www.test1.com"}]
        },
        {
            'week': '2025-W08',
            'file_path': temp_dir / 'weekly-2025-W08-interpreted.json',
            'interpretation': [{"question": "Week 8 Question", "answer": "Week 8 Answer", "site": "www.test1.com"}]
        }
    ]
    mock_interpreter_class.return_value = mock_interpreter
    
    # Create job root directory
    jobs_root = temp_dir
    
    # Call interpret_weekly with specific weeks and overwrite=True
    sites = ["www.test1.com", "www.test2.com"]
    specific_weeks = ["2025-W07", "2025-W08"]
    await interpret_weekly(jobs_root, sites, current_week_only=False, overwrite=True, specific_weeks=specific_weeks)
    
    # Verify the interpreter was called with correct parameters
    mock_interpreter.interpret_weekly.assert_called_once_with(
        job_dirs_root=jobs_root, 
        sites=sites,
        current_week_only=False,
        overwrite=True,
        specific_weeks=specific_weeks
    )
    
    # Check that weekly files were created
    assert (temp_dir / 'weekly-2025-W07-interpreted.json').exists()
    assert (temp_dir / 'weekly-2025-W08-interpreted.json').exists()


@pytest.mark.asyncio
@patch('src.media_lens.runner.generate_html_from_path')
@patch('src.media_lens.runner.upload_file')
async def test_format_and_deploy(mock_upload_file, mock_generate_html, temp_dir, mock_env_vars):
    """Test HTML formatting and deployment."""
    # Mock the HTML generator
    mock_generate_html.return_value = "<html><body>Test report</body></html>"
    
    # Create job directory and files
    jobs_root = temp_dir
    
    # Create main index file
    (jobs_root / "medialens.html").write_text("<html>Test</html>")
    
    # Create weekly files
    (jobs_root / "medialens-2025-W08.html").write_text("<html>Weekly Test 1</html>")
    (jobs_root / "medialens-2025-W09.html").write_text("<html>Weekly Test 2</html>")
    
    # Create a subdirectory with additional files
    subdir = jobs_root / "test-subdir"
    subdir.mkdir(exist_ok=True)
    (subdir / "medialens-subdir.html").write_text("<html>Subdir Test</html>")
    
    # Set environment variable for FTP path
    with patch.dict(os.environ, {"FTP_REMOTE_PATH": "/remote/path"}):
        # Call format_and_deploy
        await format_and_deploy(jobs_root)
    
    # Verify HTML generation was called
    mock_generate_html.assert_called_once()
    assert mock_generate_html.call_args[0][0] == jobs_root
    
    # Verify upload was called for main index file
    mock_upload_file.assert_any_call(jobs_root / "medialens.html", "/remote/path")
    
    # Verify upload was called for both weekly files
    mock_upload_file.assert_any_call(jobs_root / "medialens-2025-W08.html", "/remote/path")
    mock_upload_file.assert_any_call(jobs_root / "medialens-2025-W09.html", "/remote/path")
    
    # Verify upload was called for subdirectory file
    mock_upload_file.assert_any_call(subdir / "medialens-subdir.html", "/remote/path")
    
    # Verify total number of uploads
    assert mock_upload_file.call_count == 4

@pytest.mark.asyncio
@patch('src.media_lens.runner.DailySummarizer')
async def test_summarize_all(mock_summarizer_class, temp_dir, mock_env_vars):
    """Test the summarize_all function."""
    # Mock the summarizer
    mock_summarizer = MagicMock()
    mock_summarizer_class.return_value = mock_summarizer
    
    # Create job directories with UTC timestamp pattern
    for day in range(1, 4):
        job_dir = temp_dir / f"2025-03-{day:02d}T12:00:00+00:00"
        job_dir.mkdir(exist_ok=True)
        
        # Add a summary file to one directory to test skipping
        if day == 2:
            (job_dir / "daily_news.txt").write_text("Existing summary")
    
    # Call summarize_all without force
    await summarize_all(temp_dir)
    
    # Verify summarizer was called for directories without summary
    assert mock_summarizer.generate_summary_from_job_dir.call_count == 2
    
    # Call summarize_all with force=True
    mock_summarizer.generate_summary_from_job_dir.reset_mock()
    await summarize_all(temp_dir, force=True)
    
    # Verify summarizer was called for all directories when forced
    assert mock_summarizer.generate_summary_from_job_dir.call_count == 3

@pytest.mark.parametrize("steps", [
    ([Steps.HARVEST, Steps.EXTRACT]),
    ([Steps.INTERPRET, Steps.INTERPRET_WEEKLY]),
    ([Steps.SUMMARIZE_DAILY, Steps.DEPLOY]),
])
def test_steps_enum(steps):
    """Test that the Steps enum contains the expected values and no moralizer step."""
    # Convert steps to values for easier comparison
    step_values = [step.value for step in Steps]
    
    # Check that expected steps exist
    assert "harvest" in step_values
    assert "extract" in step_values
    assert "interpret" in step_values
    assert "interpret_weekly" in step_values
    assert "summarize_daily" in step_values
    assert "deploy" in step_values
    
    # Verify that moralize_weekly is not in the enum
    assert "moralize_weekly" not in step_values