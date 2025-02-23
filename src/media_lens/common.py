import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

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