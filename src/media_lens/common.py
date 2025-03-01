import datetime
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List

import pytz

UTC_PATTERN: str = r'\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d\+00:00'

LONG_DATE_PATTERN: str = "%a %d-%b-%Y %H:%M %Z"
UTC_DATE_PATTERN: str = "%Y-%m-%dT%H:%M:%S+00:00"
WEEK_KEY_FORMAT: str = "%Y-W%U"  # Year-week number format (e.g., "2025-W08")
WEEK_DISPLAY_FORMAT: str = "Week of %b %d, %Y"  # Display format (e.g., "Week of Feb 24, 2025")
TZ_DEFAULT: str = 'America/Los_Angeles'

def utc_timestamp() -> str:
    # get utc timestamp as short string
    return datetime.datetime.now(datetime.timezone.utc).isoformat(sep='T', timespec='seconds')

def timestamp_as_long_date(tz = pytz.timezone(TZ_DEFAULT)) -> str:
    dt = datetime.datetime.now(tz)
    return dt.strftime(LONG_DATE_PATTERN)

def timestamp_str_as_long_date(ts: str, tz = pytz.timezone(TZ_DEFAULT)) -> str:
    dt = datetime.datetime.fromisoformat(ts)
    dt_local = dt.astimezone(tz)
    return dt_local.strftime(LONG_DATE_PATTERN)

def get_week_key(dt: datetime.datetime, tz = pytz.timezone(TZ_DEFAULT)) -> str:
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
    first_day = datetime.datetime(year, 1, 1, tzinfo=tz)
    
    # Calculate days to add to get to the start of the desired week
    # Week 1 is the week containing Jan 1
    days_to_add = (week_num * 7) - first_day.weekday()
    if days_to_add < 0:
        days_to_add += 7
    
    # Get Monday of the target week
    week_start = first_day + datetime.timedelta(days=days_to_add)
    
    return week_start.strftime(WEEK_DISPLAY_FORMAT)

def get_datetime_from_timestamp(ts: str) -> datetime.datetime:
    """
    Convert a timestamp string to a datetime object.
    """
    return datetime.datetime.fromisoformat(ts)

def get_project_root() -> Path:
    return Path(__file__).parent.parent.parent

SITES: list[str] = [
    'www.cnn.com',
    'www.bbc.com',
    'www.foxnews.com'
]

ANTHROPIC_MODEL: str = "claude-3-5-sonnet-latest"


LOGGER_NAME: str = "MEDIA_LENS"
LOGFILE_NAME: str = "media-lens-{ts}.log"
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] <%(filename)s:%(lineno)s - %(funcName)s()> %(message)s"

def create_logger(name: str, logfile_path: Path = None) -> logging.Logger:
    logger = logging.getLogger(name)
    formatter = logging.Formatter(LOG_FORMAT)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        if logfile_path:
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