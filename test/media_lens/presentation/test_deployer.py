import datetime
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.media_lens.presentation.deployer import (
    get_deploy_cursor, update_deploy_cursor, reset_deploy_cursor, 
    get_files_to_deploy, upload_html_content_from_storage
)


def test_get_deploy_cursor_no_cursor_exists(test_storage_adapter, monkeypatch):
    """Test getting deploy cursor when no cursor file exists."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr("src.media_lens.presentation.deployer.shared_storage", test_storage_adapter)
    
    # Ensure cursor file doesn't exist
    cursor_path = "deploy_cursor.txt"
    if test_storage_adapter.file_exists(cursor_path):
        test_storage_adapter.delete_file(cursor_path)
    
    # Test getting cursor
    cursor = get_deploy_cursor()
    assert cursor is None


def test_update_and_get_deploy_cursor(test_storage_adapter, monkeypatch):
    """Test updating and getting deploy cursor."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr("src.media_lens.presentation.deployer.shared_storage", test_storage_adapter)
    
    # Test timestamp
    test_timestamp = datetime.datetime(2025, 2, 26, 15, 30, 0, tzinfo=datetime.timezone.utc)
    
    # Update cursor
    update_deploy_cursor(test_timestamp)
    
    # Get cursor back
    cursor = get_deploy_cursor()
    assert cursor is not None
    assert cursor == test_timestamp


def test_reset_deploy_cursor(test_storage_adapter, monkeypatch):
    """Test resetting deploy cursor."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr("src.media_lens.presentation.deployer.shared_storage", test_storage_adapter)
    
    # Set a cursor first
    test_timestamp = datetime.datetime(2025, 2, 26, 15, 30, 0, tzinfo=datetime.timezone.utc)
    update_deploy_cursor(test_timestamp)
    
    # Verify cursor exists
    assert get_deploy_cursor() is not None
    
    # Reset cursor
    reset_deploy_cursor()
    
    # Verify cursor is gone
    assert get_deploy_cursor() is None


def test_get_files_to_deploy_no_cursor(test_storage_adapter, monkeypatch):
    """Test getting files to deploy when no cursor exists."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr("src.media_lens.presentation.deployer.shared_storage", test_storage_adapter)
    
    # Create some test HTML files in staging directory
    staging_dir = test_storage_adapter.get_staging_directory()
    test_storage_adapter.create_directory(staging_dir)
    
    test_files = [
        f"{staging_dir}/medialens.html",
        f"{staging_dir}/medialens-2025-W09.html",
        f"{staging_dir}/medialens-2025-W10.html"
    ]
    
    for file_path in test_files:
        test_storage_adapter.write_text(file_path, "<html><body>Test</body></html>")
    
    # Get files to deploy with no cursor
    files_to_deploy = get_files_to_deploy(cursor=None)
    
    # Should return all HTML files
    assert len(files_to_deploy) == 3
    for test_file in test_files:
        assert test_file in files_to_deploy


def test_get_files_to_deploy_with_cursor(test_storage_adapter, monkeypatch):
    """Test getting files to deploy with an existing cursor."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr("src.media_lens.presentation.deployer.shared_storage", test_storage_adapter)
    
    # Create staging directory
    staging_dir = test_storage_adapter.get_staging_directory()
    test_storage_adapter.create_directory(staging_dir)
    
    # Create test files with different timestamps
    old_file = f"{staging_dir}/old_file.html"
    new_file = f"{staging_dir}/new_file.html"
    
    test_storage_adapter.write_text(old_file, "<html><body>Old</body></html>")
    test_storage_adapter.write_text(new_file, "<html><body>New</body></html>")
    
    # Get modification times
    old_mtime = test_storage_adapter.get_file_modified_time(old_file)
    new_mtime = test_storage_adapter.get_file_modified_time(new_file)
    
    # Set cursor between the two file times
    cursor = old_mtime + datetime.timedelta(seconds=1)
    
    # Get files to deploy
    files_to_deploy = get_files_to_deploy(cursor=cursor)
    
    # Should only return files newer than cursor
    if new_mtime > cursor:
        assert new_file in files_to_deploy
    if old_mtime <= cursor:
        assert old_file not in files_to_deploy


@patch('src.media_lens.presentation.deployer.upload_file')
def test_upload_html_content_from_storage(mock_upload_file, test_storage_adapter, monkeypatch):
    """Test uploading HTML content from storage."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr("src.media_lens.presentation.deployer.shared_storage", test_storage_adapter)
    
    # Create test HTML file
    test_content = "<html><body><h1>Test Content</h1></body></html>"
    test_file_path = "test/medialens.html"
    test_storage_adapter.write_text(test_file_path, test_content)
    
    # Mock upload_file to return success
    mock_upload_file.return_value = True
    
    # Call upload function
    os.environ["FTP_REMOTE_PATH"] = "/remote/path"  # Set remote path for testing
    result = upload_html_content_from_storage(test_file_path)
    
    # Verify upload_file was called
    assert mock_upload_file.called
    args, kwargs = mock_upload_file.call_args
    
    # Check that temporary file path was used
    assert isinstance(args[0], Path)
    assert args[1] == "/remote/path"
    assert args[2] == "medialens.html"  # Original filename
    
    # Verify result
    assert result is True


@patch('src.media_lens.presentation.deployer.upload_file')
def test_upload_html_content_from_storage_failure(mock_upload_file, test_storage_adapter, monkeypatch):
    """Test uploading HTML content from storage when upload fails."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr("src.media_lens.presentation.deployer.shared_storage", test_storage_adapter)
    
    # Create test HTML file
    test_content = "<html><body><h1>Test Content</h1></body></html>"
    test_file_path = "test/medialens.html"
    test_storage_adapter.write_text(test_file_path, test_content)
    
    # Mock upload_file to return failure
    mock_upload_file.return_value = False
    
    # Call upload function
    os.environ["FTP_REMOTE_PATH"] = "/remote/path"  # Set remote path for testing
    result = upload_html_content_from_storage(test_file_path)
    
    # Verify result
    assert result is False


def test_get_deploy_cursor_invalid_format(test_storage_adapter, monkeypatch):
    """Test getting deploy cursor when cursor file has invalid format."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr("src.media_lens.presentation.deployer.shared_storage", test_storage_adapter)
    
    # Create cursor file with invalid content
    cursor_path = "deploy_cursor.txt"
    test_storage_adapter.write_text(cursor_path, "invalid-timestamp-format")
    
    # Test getting cursor - should return None for invalid format
    cursor = get_deploy_cursor()
    assert cursor is None


def test_get_files_to_deploy_handles_missing_mtime(test_storage_adapter, monkeypatch):
    """Test get_files_to_deploy handles files with missing modification time."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr("src.media_lens.presentation.deployer.shared_storage", test_storage_adapter)
    
    # Create staging directory and test file
    staging_dir = test_storage_adapter.get_staging_directory()
    test_storage_adapter.create_directory(staging_dir)
    
    test_file = f"{staging_dir}/test.html"
    test_storage_adapter.write_text(test_file, "<html><body>Test</body></html>")
    
    # Create a custom mock function that will return None for the get_file_modified_time call
    original_get_mtime = test_storage_adapter.get_file_modified_time
    def mock_get_file_modified_time(path):
        if "test.html" in str(path):
            return None  # Simulate error for our test file
        return original_get_mtime(path)
    
    # Mock get_file_modified_time to return None (simulating error)
    monkeypatch.setattr(test_storage_adapter, "get_file_modified_time", mock_get_file_modified_time)
    
    # Set a cursor
    cursor = datetime.datetime.now(datetime.timezone.utc)
    
    # Get files to deploy
    files_to_deploy = get_files_to_deploy(cursor=cursor)
    
    # Should include the file even without modification time (fail-safe behavior)
    assert test_file in files_to_deploy