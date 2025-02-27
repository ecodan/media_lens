import datetime
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytz

UTC_PATTERN: str = r'\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d\+00:00'

LONG_DATE_PATTERN: str = "%a %d-%b-%Y %H:%M %Z"
UTC_DATE_PATTERN: str = "%Y-%m-%dT%H:%M:%S+00:00"
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
            handler = RotatingFileHandler(
                filename=str(logfile_path),
                maxBytes=1000000,
                backupCount = 10
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    return logger