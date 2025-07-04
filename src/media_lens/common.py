from datetime import datetime, timezone, timedelta
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Union

import pytz

UTC_REGEX_PATTERN: str = r'\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d\+00:00'
UTC_REGEX_PATTERN_BW_COMPAT: str = r'\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])_(?:[01]\d|2[0-3])[0-5]\d[0-5]\d'

LONG_DATE_PATTERN: str = "%a %d-%b-%Y %H:%M %Z"
UTC_DATE_PATTERN: str = "%Y-%m-%dT%H:%M:%S+00:00"
UTC_DATE_PATTERN_BW_COMPAT: str = "%Y-%m-%d_%H%M%S"
WEEK_KEY_FORMAT: str = "%Y-W%U"  # Year-week number format (e.g., "2025-W08")
WEEK_DISPLAY_FORMAT: str = "Week of %b %d, %Y"  # Display format (e.g., "Week of Feb 24, 2025")
TZ_DEFAULT: str = 'America/Los_Angeles'

def is_last_day_of_week(dt: datetime = None, tz = None) -> bool:
    """
    Check if the given datetime is the last day of the week (Sunday).
    If no datetime is provided, check the current day.
    
    :param dt: Datetime to check, defaults to current datetime
    :param tz: Timezone to use - if None, uses the timezone from the provided datetime object
               or UTC for the current time
    :return: True if the datetime is the last day of the week, False otherwise
    """
    if dt is None:
        # No datetime provided, use current time
        dt = datetime.now(timezone.utc)
        if tz is not None:
            dt = dt.astimezone(tz)
    # We have a datetime, but don't change its timezone unless explicitly requested
    elif tz is not None:
        # Only convert timezone if explicitly requested
        dt = dt.astimezone(tz)
    
    # In Python's datetime weekday(), Monday is 0 and Sunday is 6
    weekday_num = dt.weekday()
    
    # True if Sunday (weekday 6)
    return weekday_num == 6

def utc_timestamp() -> str:
    # get utc timestamp as short string
    return datetime.now(timezone.utc).isoformat(sep='T', timespec='seconds')

def utc_bw_compat_timestamp() -> str:
    # get compatible timestamp as short string
    return datetime.now(timezone.utc).strftime(UTC_DATE_PATTERN_BW_COMPAT)

def timestamp_as_long_date(tz = pytz.timezone(TZ_DEFAULT)) -> str:
    dt = datetime.now(tz)
    return dt.strftime(LONG_DATE_PATTERN)

def timestamp_bw_compat_str_as_long_date(ts: str, tz = pytz.timezone(TZ_DEFAULT)) -> str:
    dt = datetime.strptime(ts, UTC_DATE_PATTERN_BW_COMPAT)
    dt = dt.replace(tzinfo=timezone.utc)
    dt_local = dt.astimezone(tz)
    return dt_local.strftime(LONG_DATE_PATTERN)

def get_week_key(dt: datetime, tz = pytz.timezone(TZ_DEFAULT)) -> str:
    """
    Convert a datetime to a week identifier string (YYYY-WNN format).
    This is used for grouping data by week.
    """
    dt_local = dt.astimezone(tz)
    return dt_local.strftime(WEEK_KEY_FORMAT)

def get_week_display(week_key: str, tz = pytz.timezone(TZ_DEFAULT)) -> str:
    """
    Convert a week key (YYYY-WNN) to a display string.
    Returns the formatted date for Monday of that week.
    """
    year = int(week_key.split('-W')[0])
    week_num = int(week_key.split('-W')[1])
    
    # Get the first day of the year
    first_day = datetime(year, 1, 1, tzinfo=tz)
    
    # Calculate days to add to get to the start of the desired week
    # Week 1 is the week containing Jan 1
    days_to_add = (week_num * 7) - first_day.weekday()
    if days_to_add < 0:
        days_to_add += 7
    
    # Get Monday of the target week
    week_start = first_day + timedelta(days=days_to_add)
    
    return week_start.strftime(WEEK_DISPLAY_FORMAT)


def get_utc_datetime_from_timestamp(ts: str) -> datetime:
    """
    Convert a UTC timestamp string to a UTC datetime object.

    :param ts: Timestamp string in UTC (format: YYYY-MM-DD_HHMMSS)
    :return: UTC datetime object
    """
    dt = datetime.strptime(ts, UTC_DATE_PATTERN_BW_COMPAT)
    return dt.replace(tzinfo=timezone.utc)

def get_project_root() -> Path:
    return Path(__file__).parent.parent.parent

def get_working_dir() -> Path:
    if os.getenv("WORKING_DIR"):
        return Path(os.getenv("WORKING_DIR"))
    else:
        return Path(__file__).parent.parent.parent / "working"

SITES_DEFAULT: list[str] = [
    'www.cnn.com',
    'www.bbc.com',
    'www.foxnews.com'
]

SITES: list[str] = SITES_DEFAULT

# AI Provider Configuration
AI_PROVIDER: str = "claude"  # Options: "claude", "vertex"

# Anthropic Configuration
# ANTHROPIC_MODEL: str = "claude-3-7-sonnet-latest"
ANTHROPIC_MODEL: str = "claude-3-5-haiku-latest"

# Google Vertex AI Configuration
VERTEX_AI_PROJECT_ID: str = "medialens"
VERTEX_AI_LOCATION: str = "us-central1"
VERTEX_AI_MODEL: str = "gemini-2.5-flash"


LOGGER_NAME: str = "MEDIA_LENS"
LOGFILE_NAME: str = "media-lens-{ts}.log"
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] <%(filename)s:%(lineno)s - %(funcName)s()> %(message)s"

# Global run state
class RunState:
    _should_stop = False
    _current_run_id = None
    
    @classmethod
    def stop_requested(cls) -> bool:
        """Check if stop has been requested for the current run"""
        return cls._should_stop
    
    @classmethod
    def request_stop(cls) -> None:
        """Request the current run to stop"""
        cls._should_stop = True
        logger = logging.getLogger(LOGGER_NAME)
        logger.info(f"Stop requested for run {cls._current_run_id}")
    
    @classmethod
    def reset(cls, run_id: str = None) -> None:
        """Reset the stop flag, optionally setting a new run ID"""
        cls._should_stop = False
        cls._current_run_id = run_id
        
    @classmethod
    def get_run_id(cls) -> str:
        """Get the current run ID"""
        return cls._current_run_id

def create_logger(name: str, logfile_path: Union[str, Path] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    formatter = logging.Formatter(LOG_FORMAT)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        if logfile_path:
            # Convert string path to Path object if necessary
            if isinstance(logfile_path, str):
                logfile_path = Path(logfile_path)
                
            if not logfile_path.parent.exists():
                raise ValueError(f"Logfile path does not exist: {logfile_path.parent}")
            handler = RotatingFileHandler(
                filename=str(logfile_path),
                maxBytes=1000000,
                backupCount = 10
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    return logger


def ensure_secrets_loaded():
    """Ensure that secrets are loaded from Google Cloud Secret Manager if available.
    
    This function should be called at application startup to load secrets
    before they are needed by other components.
    """
    try:
        from .secret_manager import load_secrets_from_gcp
        loaded_secrets = load_secrets_from_gcp()
        
        logger = logging.getLogger(LOGGER_NAME)
        logger.info("Secrets initialization completed")
        
        # Log which secrets were loaded (without values)
        for key, value in loaded_secrets.items():
            status = "loaded" if value else "not_available"
            logger.debug(f"Secret {key}: {status}")
            
        return loaded_secrets
        
    except Exception as e:
        logger = logging.getLogger(LOGGER_NAME)
        logger.error(f"Failed to load secrets: {e}")
        return {}