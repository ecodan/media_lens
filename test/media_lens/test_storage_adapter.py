import os
import pytest
import tempfile
import shutil
import json
from pathlib import Path

from src.media_lens.storage_adapter import StorageAdapter

@pytest.fixture
def test_files():
    temp_dir = tempfile.mkdtemp()
    test_file_path = Path(temp_dir) / "test_file.txt"
    with open(test_file_path, "w") as f:
        f.write("test content")

    yield {"dir": temp_dir, "file": test_file_path}
    shutil.rmtree(temp_dir)

@pytest.fixture
def temp_test_dir():
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def storage_adapter(monkeypatch, temp_test_dir):
    """Create a storage adapter instance for testing"""
    # Set environment for local testing
    monkeypatch.setenv("USE_CLOUD_STORAGE", "false")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(temp_test_dir))
    
    return StorageAdapter()

def test_storage_adapter_local(test_files, monkeypatch):
    # Set environment for local testing
    monkeypatch.setenv("USE_CLOUD_STORAGE", "false")

    # Create a temporary directory for the local storage root
    local_root = tempfile.mkdtemp()
    monkeypatch.setenv("LOCAL_STORAGE_PATH", local_root)

    adapter = StorageAdapter()

    # Test upload
    remote_path = "test/test_file.txt"
    adapter.upload_file(test_files["file"], remote_path)

    # Test file exists
    assert adapter.file_exists(remote_path)

    # Test list files
    files = adapter.list_files("test")
    assert len(files) == 1
    assert files[0] == remote_path

    # Test download
    download_path = Path(test_files["dir"]) / "downloaded.txt"
    adapter.download_file(remote_path, download_path)

    assert download_path.exists()
    with open(download_path, "r") as f:
        assert f.read() == "test content"

    # Clean up
    shutil.rmtree(local_root)

class TestStorageAdapter:
    
    def test_write_read_text(self, storage_adapter, temp_test_dir):
        """Test writing and reading text content"""
        test_content = "This is test content"
        file_path = "test-file.txt"
        
        # Write content
        result_path = storage_adapter.write_text(file_path, test_content)
        assert Path(result_path).exists()
        
        # Read content back
        read_content = storage_adapter.read_text(file_path)
        assert read_content == test_content
    
    def test_write_read_json(self, storage_adapter):
        """Test writing and reading JSON data"""
        test_data = {"name": "test", "values": [1, 2, 3], "nested": {"key": "value"}}
        file_path = "test-data.json"
        
        # Write JSON
        result_path = storage_adapter.write_json(file_path, test_data)
        assert storage_adapter.file_exists(file_path)
        
        # Read JSON back
        read_data = storage_adapter.read_json(file_path)
        assert read_data == test_data
    
    def test_file_exists(self, storage_adapter):
        """Test file existence check"""
        # File should not exist yet
        assert not storage_adapter.file_exists("nonexistent.txt")
        
        # Create file
        storage_adapter.write_text("exists.txt", "content")
        
        # File should exist now
        assert storage_adapter.file_exists("exists.txt")
    
    def test_create_directory(self, storage_adapter):
        """Test directory creation"""
        dir_path = "test/nested/directory"
        
        # Create directory
        result_path = storage_adapter.create_directory(dir_path)
        
        # Check if directory exists
        assert Path(result_path).exists()
        assert Path(result_path).is_dir()
    
    def test_list_files(self, storage_adapter):
        """Test listing files"""
        # Create some test files
        storage_adapter.write_text("file1.txt", "content1")
        storage_adapter.write_text("file2.txt", "content2")
        storage_adapter.write_text("test/file3.txt", "content3")
        
        # List all files
        all_files = storage_adapter.list_files()
        assert len(all_files) == 3
        assert "file1.txt" in all_files
        assert "file2.txt" in all_files
        assert "test/file3.txt" in all_files
        
        # List files with prefix
        test_files = storage_adapter.list_files("test")
        assert len(test_files) == 1
        assert "test/file3.txt" in test_files
    
    def test_get_files_by_pattern(self, storage_adapter):
        """Test finding files by pattern"""
        # Create test files
        storage_adapter.write_text("test1.txt", "content")
        storage_adapter.write_text("test2.txt", "content")
        storage_adapter.write_text("other.txt", "content")
        storage_adapter.write_text("test.json", "content")
        
        # Find files by pattern
        txt_files = storage_adapter.get_files_by_pattern("", "*.txt")
        assert len(txt_files) == 3
        assert all(f.endswith(".txt") for f in txt_files)
        
        test_files = storage_adapter.get_files_by_pattern("", "test*.txt")
        assert len(test_files) == 2
        assert all(f.startswith("test") and f.endswith(".txt") for f in test_files)
    
    def test_get_absolute_path(self, storage_adapter, temp_test_dir):
        """Test getting absolute path"""
        rel_path = "test/file.txt"
        abs_path = storage_adapter.get_absolute_path(rel_path)
        
        expected_path = str(temp_test_dir / rel_path)
        assert abs_path == expected_path
    
    def test_write_read_binary(self, storage_adapter):
        """Test writing and reading binary content"""
        binary_content = b'\x00\x01\x02\x03\x04'
        file_path = "binary.bin"
        
        # Write binary
        storage_adapter.write_binary(file_path, binary_content)
        
        # Read binary back
        read_binary = storage_adapter.read_binary(file_path)
        assert read_binary == binary_content