import datetime
import re
from pathlib import Path

import pytest
import pytz

from src.media_lens.common import (
    utc_timestamp, timestamp_as_long_date, timestamp_bw_compat_str_as_long_date,
    get_week_key, get_week_display, get_utc_datetime_from_timestamp,
    get_project_root, create_logger, WEEK_KEY_FORMAT, LOGGER_NAME,
    UTC_REGEX_PATTERN_BW_COMPAT
)


def test_utc_timestamp():
    """Test that utc_timestamp returns a properly formatted UTC timestamp."""
    timestamp = utc_timestamp()
    
    # Verify format with regex pattern - utc_timestamp uses UTC_DATE_PATTERN not UTC_DATE_PATTERN_BW_COMPAT
    # Should match ISO8601 format
    assert isinstance(timestamp, str)
    assert 'T' in timestamp
    assert '+00:00' in timestamp
    
    # Verify it's a valid ISO format timestamp
    try:
        dt = datetime.datetime.fromisoformat(timestamp)
        assert dt.tzinfo is not None  # Should have timezone info
    except ValueError:
        pytest.fail("Generated timestamp is not a valid ISO format")


def test_timestamp_as_long_date():
    """Test that timestamp_as_long_date returns formatted date string."""
    long_date = timestamp_as_long_date()
    
    # Should be in format like "Mon 26-Feb-2024 22:30 PST"
    assert isinstance(long_date, str)
    assert len(long_date) > 10  # Basic sanity check


def test_timestamp_str_as_long_date():
    """Test converting ISO timestamp to long date format."""
    # Create a test timestamp in backwards compatible format
    test_ts = "2025-02-26_153000"
    
    # Convert to long date
    long_date = timestamp_bw_compat_str_as_long_date(test_ts)
    
    # Verify conversion
    assert isinstance(long_date, str)
    assert "26-Feb-2025" in long_date  # Should contain the date
    
    # Test with explicit timezone
    test_tz = pytz.timezone('America/New_York')
    long_date_ny = timestamp_bw_compat_str_as_long_date(test_ts, test_tz)
    
    # NY time should be different from default
    assert long_date != long_date_ny


def test_get_week_key():
    """Test week key generation from datetime."""
    # Create a test datetime
    test_dt = datetime.datetime(2025, 2, 26, 15, 30, 0, tzinfo=pytz.UTC)
    
    # Get week key
    week_key = get_week_key(test_dt)
    
    # Should match YYYY-WNN format
    assert re.match(r'^\d{4}-W\d{2}$', week_key)
    
    # Test with different timezone
    test_tz = pytz.timezone('America/New_York')
    week_key_ny = get_week_key(test_dt, test_tz)
    
    # The week key may or may not change depending on the day and time
    # Just ensure it's in the right format
    assert re.match(r'^\d{4}-W\d{2}$', week_key_ny)


def test_get_week_display():
    """Test converting week key to display format."""
    # Test with a known week key
    week_key = "2025-W08"
    display = get_week_display(week_key)
    
    # Should contain month and year
    assert "2025" in display
    assert isinstance(display, str)


def test_get_datetime_from_timestamp():
    """Test converting timestamp string to datetime."""
    # Create a test timestamp in backwards compatible format
    test_ts = "2025-02-26_153000"
    
    # Convert to datetime
    dt = get_utc_datetime_from_timestamp(test_ts)
    
    # Verify conversion
    assert isinstance(dt, datetime.datetime)
    assert dt.year == 2025
    assert dt.month == 2
    assert dt.day == 26
    assert dt.hour == 15
    assert dt.minute == 30
    assert dt.second == 0
    assert dt.tzinfo is not None  # Should have timezone info


def test_get_project_root():
    """Test that get_project_root returns a valid Path object."""
    root = get_project_root()
    
    # Verify it's a Path object
    assert isinstance(root, Path)
    assert root.exists()
    
    # Verify it points to a directory that contains key project files
    assert (root / "src").exists()


def test_create_logger():
    """Test logger creation and configuration."""
    # Create logger with no file
    logger = create_logger(LOGGER_NAME)
    
    # Verify logger properties
    assert logger.name == LOGGER_NAME
    assert logger.level == 10  # DEBUG level
    assert len(logger.handlers) > 0  # Should have at least one handler
    
    # Skip testing the error case - it's difficult to predict exactly what will
    # happen on different systems when trying to access an invalid path