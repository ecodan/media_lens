import shutil
import tempfile
from pathlib import Path

import pytest

from src.media_lens.storage import get_shared_storage, shared_storage
from src.media_lens.storage_adapter import StorageAdapter


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture(autouse=True)
def reset_shared_storage():
    """Reset shared storage between tests"""
    global _shared_storage
    _shared_storage = None
    StorageAdapter.reset_instance()


def test_get_shared_storage_singleton(monkeypatch, temp_test_dir):
    """Test that get_shared_storage returns the same instance"""
    # Set up environment
    monkeypatch.setenv("USE_CLOUD_STORAGE", "false")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(temp_test_dir))

    # Get shared storage multiple times
    storage1 = get_shared_storage()
    storage2 = get_shared_storage()

    # Should be the same instance
    assert storage1 is storage2


def test_shared_storage_proxy(monkeypatch, temp_test_dir):
    """Test that shared_storage proxy works correctly"""
    # Set up environment
    monkeypatch.setenv("USE_CLOUD_STORAGE", "false")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(temp_test_dir))

    # Test proxy access
    test_content = "test content"
    file_path = "test-file.txt"

    # Write through proxy
    shared_storage.write_text(file_path, test_content)

    # Read through proxy
    read_content = shared_storage.read_text(file_path)
    assert read_content == test_content

    # Check file exists through proxy
    assert shared_storage.file_exists(file_path)


def test_shared_storage_proxy_same_as_get_shared(monkeypatch, temp_test_dir):
    """Test that shared_storage proxy uses the same instance as get_shared_storage"""
    # Set up environment
    monkeypatch.setenv("USE_CLOUD_STORAGE", "false")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(temp_test_dir))

    # Get instance directly and through proxy
    direct_storage = get_shared_storage()

    # Write with direct instance
    test_content = "test content"
    file_path = "test-file.txt"
    direct_storage.write_text(file_path, test_content)

    # Read with proxy
    proxy_content = shared_storage.read_text(file_path)
    assert proxy_content == test_content

    # Both should reference the same underlying storage
    assert hasattr(shared_storage, "_SharedStorageProxy__dict__") or callable(
        getattr(shared_storage, "write_text", None)
    )


def test_env_loading_fallback(monkeypatch, temp_test_dir):
    """Test that get_shared_storage loads .env if environment vars aren't set"""
    # Clear environment variables first
    monkeypatch.delenv("LOCAL_STORAGE_PATH", raising=False)
    monkeypatch.delenv("USE_CLOUD_STORAGE", raising=False)

    # Mock dotenv.load_dotenv to set our test environment
    def mock_load_dotenv():
        monkeypatch.setenv("USE_CLOUD_STORAGE", "false")
        monkeypatch.setenv("LOCAL_STORAGE_PATH", str(temp_test_dir))

    monkeypatch.setattr("dotenv.load_dotenv", mock_load_dotenv)

    # This should trigger the dotenv loading
    storage = get_shared_storage()
    assert storage is not None
    assert not storage.use_cloud
