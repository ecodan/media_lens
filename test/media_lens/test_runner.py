import datetime
import os
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
import sys

import pytest

from src.media_lens.runner import (
    extract, interpret, interpret_weekly, format_output, deploy_output, Steps, summarize_all,
    validate_step_combinations, scrape, clean, main
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
    
    # Call interpret - convert Path to string since function expects string
    await interpret(str(job_dir), sites)
    
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
    await interpret_weekly(current_week_only=True)
    
    # Verify the interpreter was called
    mock_interpreter.interpret_weeks.assert_called_once()
    
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
    await interpret_weekly(current_week_only=False, overwrite=True, specific_weeks=specific_weeks)
    
    # Verify the interpreter was called
    mock_interpreter.interpret_weeks.assert_called_once()
    
    # Check that weekly files were created
    assert (temp_dir / 'weekly-2025-W07-interpreted.json').exists()
    assert (temp_dir / 'weekly-2025-W08-interpreted.json').exists()


@pytest.mark.asyncio
@patch('src.media_lens.runner.generate_html_from_path')
async def test_format_output(mock_generate_html, temp_dir, mock_env_vars):
    """Test HTML formatting."""
    # Mock the HTML generator
    mock_generate_html.return_value = "<html><body>Test report</body></html>"
    
    # Call format_output
    await format_output()
    
    # Verify HTML generation was called
    mock_generate_html.assert_called_once()

@pytest.mark.asyncio
@patch('src.media_lens.runner.DailySummarizer')
@patch('src.media_lens.runner.storage')
async def test_summarize_all(mock_storage, mock_summarizer_class, temp_dir, mock_env_vars):
    """Test the summarize_all function."""
    # Mock the summarizer
    mock_summarizer = MagicMock()
    mock_summarizer_class.return_value = mock_summarizer
    
    # Mock storage to return job directories in legacy format
    mock_storage.list_directories.return_value = [
        "2025-03-01_120000",
        "2025-03-02_120000", 
        "2025-03-03_120000",
        "other-dir"  # This should be ignored
    ]
    
    # Mock file_exists to return True for one directory (to test skipping)
    def mock_file_exists(path):
        return path == "2025-03-02_120000/daily_news.txt"
    mock_storage.file_exists.side_effect = mock_file_exists
    
    # Call summarize_all without force
    await summarize_all(force=False)
    
    # Verify summarizer was called for directories without summary (should be 2 out of 3)
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
    assert "harvest_scrape" in step_values
    assert "harvest_clean" in step_values
    assert "extract" in step_values
    assert "interpret" in step_values
    assert "interpret_weekly" in step_values
    assert "summarize_daily" in step_values
    assert "deploy" in step_values
    
    # Verify that moralize_weekly is not in the enum
    assert "moralize_weekly" not in step_values


def test_validate_step_combinations_valid():
    """Test validation with valid step combinations."""
    # Test single steps - should all be valid
    validate_step_combinations([Steps.HARVEST])
    validate_step_combinations([Steps.HARVEST_SCRAPE])
    validate_step_combinations([Steps.HARVEST_CLEAN])
    
    # Test sequential scrape + clean - should be valid
    validate_step_combinations([Steps.HARVEST_SCRAPE, Steps.HARVEST_CLEAN])
    
    # Test other step combinations - should be valid
    validate_step_combinations([Steps.EXTRACT, Steps.INTERPRET])
    validate_step_combinations([Steps.HARVEST_SCRAPE, Steps.EXTRACT, Steps.FORMAT])


def test_validate_step_combinations_invalid():
    """Test validation with invalid step combinations."""
    # Test harvest + harvest_scrape - should be invalid
    with pytest.raises(ValueError, match="Cannot combine 'harvest' with 'harvest_scrape'"):
        validate_step_combinations([Steps.HARVEST, Steps.HARVEST_SCRAPE])
    
    # Test harvest + harvest_clean - should be invalid
    with pytest.raises(ValueError, match="Cannot combine 'harvest' with 'harvest_clean'"):
        validate_step_combinations([Steps.HARVEST, Steps.HARVEST_CLEAN])
    
    # Test harvest + both sub-steps - should be invalid
    with pytest.raises(ValueError, match="Cannot combine 'harvest' with 'harvest_scrape'"):
        validate_step_combinations([Steps.HARVEST, Steps.HARVEST_SCRAPE, Steps.HARVEST_CLEAN])


@pytest.mark.asyncio
@patch('src.media_lens.runner.Harvester')
async def test_scrape_function(mock_harvester_class, mock_env_vars):
    """Test the scrape function."""
    # Mock the harvester
    mock_harvester = AsyncMock()
    mock_harvester.scrape_sites.return_value = "jobs/2025/06/07/120000"
    mock_harvester_class.return_value = mock_harvester
    
    # Test sites
    sites = ["cnn.com", "bbc.com"]
    
    # Call scrape function
    job_dir = await scrape(sites)
    
    # Verify harvester was created and called correctly
    mock_harvester_class.assert_called_once()
    mock_harvester.scrape_sites.assert_called_once_with(sites=sites)
    assert job_dir == "jobs/2025/06/07/120000"


@pytest.mark.asyncio
@patch('src.media_lens.runner.Harvester')
async def test_clean_function(mock_harvester_class, mock_env_vars):
    """Test the clean function."""
    # Mock the harvester
    mock_harvester = AsyncMock()
    mock_harvester_class.return_value = mock_harvester
    
    # Test parameters
    job_dir = "jobs/2025/06/07/120000"
    sites = ["cnn.com", "bbc.com"]
    
    # Call clean function
    await clean(job_dir, sites)
    
    # Verify harvester was created and called correctly
    mock_harvester_class.assert_called_once()
    mock_harvester.clean_sites.assert_called_once_with(job_dir=job_dir, sites=sites)


@pytest.mark.asyncio
@patch('src.media_lens.runner.generate_html_from_path')
async def test_format_output_with_force_full(mock_generate_html, mock_env_vars):
    """Test format_output with force_full parameter."""
    # Mock the HTML generator
    mock_generate_html.return_value = "<html><body>Test report</body></html>"
    
    # Call format_output with force_full=True
    await format_output(force_full=True)
    
    # Verify HTML generation was called with force_full=True
    mock_generate_html.assert_called_once()
    args, kwargs = mock_generate_html.call_args
    assert kwargs.get('force_full') is True


@pytest.mark.asyncio
@patch('src.media_lens.runner.upload_html_content_from_storage')
@patch('src.media_lens.runner.get_files_to_deploy')
@patch('src.media_lens.runner.get_deploy_cursor')
@patch('src.media_lens.runner.update_deploy_cursor')
@patch('src.media_lens.runner.storage')
async def test_deploy_output_with_cursor(mock_storage, mock_update_cursor, mock_get_cursor, 
                                         mock_get_files, mock_upload, mock_env_vars):
    """Test deploy_output with cursor functionality."""
    # Mock environment variables
    with patch.dict(os.environ, {"FTP_REMOTE_PATH": "/remote/path"}):
        # Mock cursor and files
        mock_get_cursor.return_value = datetime.datetime.now(datetime.timezone.utc)
        mock_files = ["staging/medialens.html", "staging/medialens-2025-W09.html"]
        mock_get_files.return_value = mock_files
        
        # Mock file modification times
        def mock_get_file_modified_time(path):
            return datetime.datetime.now(datetime.timezone.utc)
        mock_storage.get_file_modified_time = mock_get_file_modified_time
        
        # Mock successful uploads
        mock_upload.return_value = True
        
        # Call deploy_output
        await deploy_output(force_full=False)
        
        # Verify cursor functions were called
        mock_get_cursor.assert_called_once()
        mock_get_files.assert_called_once()
        
        # Verify uploads were attempted
        assert mock_upload.call_count == len(mock_files)
        
        # Verify cursor was updated
        mock_update_cursor.assert_called_once()


@pytest.mark.asyncio
@patch('src.media_lens.runner.upload_html_content_from_storage')
@patch('src.media_lens.runner.get_files_to_deploy')
@patch('src.media_lens.runner.get_deploy_cursor')
async def test_deploy_output_no_files_to_deploy(mock_get_cursor, mock_get_files, mock_upload, mock_env_vars):
    """Test deploy_output when no files need deployment."""
    # Mock environment variables
    with patch.dict(os.environ, {"FTP_REMOTE_PATH": "/remote/path"}):
        # Mock cursor exists and no files to deploy
        mock_get_cursor.return_value = datetime.datetime.now(datetime.timezone.utc)
        mock_get_files.return_value = []
        
        # Call deploy_output
        await deploy_output(force_full=False)
        
        # Verify no uploads were attempted
        mock_upload.assert_not_called()


# CLI integration tests for cursor functionality

@patch('src.media_lens.runner.reset_format_cursor')
@patch('src.media_lens.runner.reset_deploy_cursor')
def test_reset_cursor_command_all(mock_reset_deploy, mock_reset_format, capsys):
    """Test reset-cursor command with --all flag."""
    # Mock sys.argv
    test_args = ['runner.py', 'reset-cursor', '--all']
    with patch.object(sys, 'argv', test_args):
        try:
            main()
        except SystemExit:
            pass  # main() calls parser which may exit
    
    # Both cursors should be reset
    mock_reset_format.assert_called_once()
    mock_reset_deploy.assert_called_once()


@patch('src.media_lens.runner.reset_format_cursor')
@patch('src.media_lens.runner.reset_deploy_cursor')
def test_reset_cursor_command_format_only(mock_reset_deploy, mock_reset_format, capsys):
    """Test reset-cursor command with --format flag."""
    # Mock sys.argv
    test_args = ['runner.py', 'reset-cursor', '--format']
    with patch.object(sys, 'argv', test_args):
        try:
            main()
        except SystemExit:
            pass
    
    # Only format cursor should be reset
    mock_reset_format.assert_called_once()
    mock_reset_deploy.assert_not_called()


@patch('src.media_lens.runner.reset_format_cursor')
@patch('src.media_lens.runner.reset_deploy_cursor')
def test_reset_cursor_command_deploy_only(mock_reset_deploy, mock_reset_format, capsys):
    """Test reset-cursor command with --deploy flag."""
    # Mock sys.argv
    test_args = ['runner.py', 'reset-cursor', '--deploy']
    with patch.object(sys, 'argv', test_args):
        try:
            main()
        except SystemExit:
            pass
    
    # Only deploy cursor should be reset
    mock_reset_deploy.assert_called_once()
    mock_reset_format.assert_not_called()


@patch('src.media_lens.runner.reset_format_cursor')
@patch('src.media_lens.runner.reset_deploy_cursor')
def test_reset_cursor_command_no_flags(mock_reset_deploy, mock_reset_format, capsys):
    """Test reset-cursor command with no specific flags (should reset both)."""
    # Mock sys.argv
    test_args = ['runner.py', 'reset-cursor']
    with patch.object(sys, 'argv', test_args):
        try:
            main()
        except SystemExit:
            pass
    
    # Both cursors should be reset when no flags specified
    mock_reset_format.assert_called_once()
    mock_reset_deploy.assert_called_once()


@patch('src.media_lens.runner.run')
@patch('src.media_lens.runner.asyncio.run')
def test_run_command_with_force_flags(mock_asyncio_run, mock_run, capsys):
    """Test run command with force flags."""
    # Mock run function to avoid actual execution
    mock_run.return_value = {"run_id": "test", "status": "success", "completed_steps": [], "error": None}
    
    # Mock sys.argv with force flags
    test_args = ['runner.py', 'run', '-s', 'format', 'deploy', '--force-full-format', '--force-full-deploy']
    with patch.object(sys, 'argv', test_args):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
            try:
                main()
            except SystemExit:
                pass
    
    # Verify asyncio.run was called
    mock_asyncio_run.assert_called_once()
    
    # Verify that run was called with the correct force flags
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    
    # Check that force flags were passed through
    assert kwargs.get('force_full_format', False) == True
    assert kwargs.get('force_full_deploy', False) == True


@patch('src.media_lens.runner.format_output')
@patch('src.media_lens.runner.deploy_output')  
@patch('src.media_lens.runner.run')
async def test_run_function_with_force_flags(mock_run_impl, mock_deploy, mock_format):
    """Test run function passes force flags to format and deploy."""
    from src.media_lens.runner import run
    
    # Mock the format and deploy functions
    mock_format.return_value = None
    mock_deploy.return_value = None
    
    # Call run with force flags
    result = await run(
        steps=[Steps.FORMAT, Steps.DEPLOY],
        force_full_format=True,
        force_full_deploy=True
    )
    
    # Verify force flags were passed to format and deploy
    mock_format.assert_called_once_with(force_full=True)
    mock_deploy.assert_called_once_with(force_full=True)