"""
Shared storage adapter instance for the media lens application.

This module provides a singleton StorageAdapter instance that should be used
throughout the application instead of creating multiple instances.
"""

import logging

from src.media_lens.common import LOGGER_NAME
from src.media_lens.storage_adapter import StorageAdapter

logger = logging.getLogger(LOGGER_NAME)

# Lazy-loaded shared instance to ensure .env is loaded first
_shared_storage = None


def get_shared_storage():
    """Get the shared storage adapter instance, creating it if needed."""
    global _shared_storage
    if _shared_storage is None:
        # Ensure .env is loaded before creating the storage adapter
        import os

        import dotenv

        if not os.getenv("LOCAL_STORAGE_PATH") and not os.getenv("USE_CLOUD_STORAGE"):
            # Try to load .env if environment variables aren't set
            dotenv.load_dotenv()
        logger.info("Creating shared storage adapter instance")
        _shared_storage = StorageAdapter.get_instance()
    return _shared_storage


# Create a property-like access for backward compatibility
class _SharedStorageProxy:
    def __getattr__(self, name):
        return getattr(get_shared_storage(), name)


shared_storage = _SharedStorageProxy()
