import datetime
from unittest.mock import MagicMock

import pytest

from src.media_lens.job_dir import JobDir


def test_jobdir_from_path_hierarchical():
    """Test creating JobDir from hierarchical path format."""
    path = "jobs/2025/06/07/193355"
    job_dir = JobDir.from_path(path)
    
    assert job_dir.storage_path == "jobs/2025/06/07/193355"
    assert job_dir.timestamp_str == "2025-06-07_193355"
    assert job_dir.is_hierarchical is True
    assert job_dir.week_key == "2025-W22"  # June 7, 2025 is in week 22
    assert isinstance(job_dir.datetime, datetime.datetime)


def test_jobdir_from_path_legacy():
    """Test creating JobDir from legacy path format."""
    path = "2025-06-07_193355"
    job_dir = JobDir.from_path(path)
    
    assert job_dir.storage_path == "2025-06-07_193355"
    assert job_dir.timestamp_str == "2025-06-07_193355"
    assert job_dir.is_hierarchical is False
    assert job_dir.week_key == "2025-W22"  # June 7, 2025 is in week 22
    assert isinstance(job_dir.datetime, datetime.datetime)


def test_jobdir_from_path_invalid():
    """Test that invalid paths raise ValueError."""
    invalid_paths = [
        "invalid/path",
        "jobs/2025/06/07",  # Missing timestamp
        "jobs/2025/06/07/12345",  # Invalid timestamp (5 digits)
        "jobs/2025/06/07/1234567",  # Invalid timestamp (7 digits)
        "jobs/2025/06/07/abcdef",  # Non-numeric timestamp
        "not-a-timestamp",
        "",
    ]
    
    for path in invalid_paths:
        with pytest.raises(ValueError):
            JobDir.from_path(path)


def test_jobdir_sorting():
    """Test that JobDir objects sort chronologically."""
    # Create JobDirs in random order
    job_dirs = [
        JobDir.from_path("2025-06-07_193355"),
        JobDir.from_path("jobs/2025/06/06/120000"),
        JobDir.from_path("2025-06-08_090000"),
        JobDir.from_path("jobs/2025/06/07/080000"),
    ]
    
    # Sort them
    sorted_dirs = sorted(job_dirs)
    
    # Check they're in chronological order
    expected_order = [
        "2025-06-06_120000",
        "2025-06-07_080000", 
        "2025-06-07_193355",
        "2025-06-08_090000",
    ]
    
    for i, expected_timestamp in enumerate(expected_order):
        assert sorted_dirs[i].timestamp_str == expected_timestamp


def test_jobdir_equality():
    """Test JobDir equality based on timestamp."""
    job_dir1 = JobDir.from_path("2025-06-07_193355")
    job_dir2 = JobDir.from_path("jobs/2025/06/07/193355")  # Same timestamp, different format
    job_dir3 = JobDir.from_path("2025-06-07_193356")  # Different timestamp
    
    assert job_dir1 == job_dir2  # Same timestamp
    assert job_dir1 != job_dir3  # Different timestamp
    assert job_dir2 != job_dir3  # Different timestamp


def test_jobdir_hash():
    """Test JobDir can be used in sets and dicts."""
    job_dir1 = JobDir.from_path("2025-06-07_193355")
    job_dir2 = JobDir.from_path("jobs/2025/06/07/193355")  # Same timestamp
    job_dir3 = JobDir.from_path("2025-06-07_193356")  # Different timestamp
    
    # Test in set (should deduplicate based on timestamp)
    job_set = {job_dir1, job_dir2, job_dir3}
    assert len(job_set) == 2  # job_dir1 and job_dir2 are the same
    
    # Test as dict key
    job_dict = {job_dir1: "value1", job_dir2: "value2", job_dir3: "value3"}
    assert len(job_dict) == 2  # job_dir1 and job_dir2 use same key


def test_jobdir_string_representation():
    """Test string representations of JobDir."""
    hierarchical_job = JobDir.from_path("jobs/2025/06/07/193355")
    legacy_job = JobDir.from_path("2025-06-07_193355")
    
    assert str(hierarchical_job) == "jobs/2025/06/07/193355"
    assert str(legacy_job) == "2025-06-07_193355"
    
    assert "hierarchical" in repr(hierarchical_job)
    assert "legacy" in repr(legacy_job)


def test_jobdir_list_all():
    """Test listing all job directories from storage."""
    # Mock storage adapter
    mock_storage = MagicMock()
    mock_storage.list_directories.return_value = [
        "jobs/2025/06/07/193355",
        "jobs/2025/06/06/120000",
        "2025-06-08_090000",
        "invalid/directory",
        "not-a-job",
        "jobs/2025/invalid",
    ]
    
    job_dirs = JobDir.list_all(mock_storage)
    
    # Should return 3 valid JobDir objects, sorted chronologically
    assert len(job_dirs) == 3
    assert job_dirs[0].timestamp_str == "2025-06-06_120000"
    assert job_dirs[1].timestamp_str == "2025-06-07_193355"
    assert job_dirs[2].timestamp_str == "2025-06-08_090000"


def test_jobdir_find_latest():
    """Test finding the latest job directory."""
    # Mock storage adapter
    mock_storage = MagicMock()
    mock_storage.list_directories.return_value = [
        "jobs/2025/06/07/193355",
        "jobs/2025/06/06/120000",
        "2025-06-08_090000",
    ]
    
    latest_job = JobDir.find_latest(mock_storage)
    
    assert latest_job is not None
    assert latest_job.timestamp_str == "2025-06-08_090000"


def test_jobdir_find_latest_empty():
    """Test finding latest when no jobs exist."""
    mock_storage = MagicMock()
    mock_storage.list_directories.return_value = []
    
    latest_job = JobDir.find_latest(mock_storage)
    
    assert latest_job is None


def test_jobdir_group_by_week():
    """Test grouping job directories by week."""
    job_dirs = [
        JobDir.from_path("2025-06-02_120000"),  # Monday, Week 22
        JobDir.from_path("2025-06-07_193355"),  # Saturday, Week 22
        JobDir.from_path("2025-06-08_090000"),  # Sunday, Week 23
        JobDir.from_path("2025-06-09_100000"),  # Monday, Week 23
    ]
    
    weeks = JobDir.group_by_week(job_dirs)
    
    assert len(weeks) == 2
    assert "2025-W22" in weeks
    assert "2025-W23" in weeks
    assert len(weeks["2025-W22"]) == 2
    assert len(weeks["2025-W23"]) == 2


def test_jobdir_properties():
    """Test JobDir properties provide correct values."""
    job_dir = JobDir.from_path("jobs/2025/06/07/193355")
    
    # Test datetime property
    expected_datetime = datetime.datetime(2025, 6, 7, 19, 33, 55, tzinfo=datetime.timezone.utc)
    assert job_dir.datetime == expected_datetime
    
    # Test week_key property 
    assert job_dir.week_key == "2025-W22"
    
    # Test storage_path property
    assert job_dir.storage_path == "jobs/2025/06/07/193355"
    
    # Test timestamp_str property
    assert job_dir.timestamp_str == "2025-06-07_193355"
    
    # Test is_hierarchical property
    assert job_dir.is_hierarchical is True


def test_jobdir_edge_cases():
    """Test edge cases for JobDir parsing."""
    # Test with trailing slashes
    job_dir1 = JobDir.from_path("jobs/2025/06/07/193355/")
    assert job_dir1.storage_path == "jobs/2025/06/07/193355"
    
    # Test with leading/trailing spaces
    job_dir2 = JobDir.from_path("  2025-06-07_193355  ")
    assert job_dir2.storage_path == "2025-06-07_193355"