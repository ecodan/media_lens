import datetime
import re
from pathlib import Path
from typing import List, Optional, Union

from src.media_lens.common import (
    UTC_REGEX_PATTERN_BW_COMPAT, 
    get_utc_datetime_from_timestamp, 
    get_week_key
)


class JobDir:
    """
    Represents a job directory with unified handling of hierarchical and legacy formats.
    
    Supports:
    - Hierarchical: jobs/2025/06/07/193355
    - Legacy: 2025-06-07_193355
    
    Provides chronological sorting, timestamp extraction, and storage path generation.
    """
    
    def __init__(self, storage_path: str, timestamp_str: str, is_hierarchical: bool):
        """
        Initialize a JobDir instance.
        
        Args:
            storage_path: Full path for storage operations
            timestamp_str: Timestamp in YYYY-MM-DD_HHMMSS format
            is_hierarchical: True if hierarchical format, False if legacy
        """
        self._storage_path = storage_path
        self._timestamp_str = timestamp_str
        self._is_hierarchical = is_hierarchical
        self._datetime = get_utc_datetime_from_timestamp(timestamp_str)
        self._week_key = get_week_key(self._datetime)
    
    @classmethod
    def from_path(cls, path: str) -> 'JobDir':
        """
        Create a JobDir from a directory path.
        
        Args:
            path: Directory path (hierarchical or legacy format)
            
        Returns:
            JobDir instance
            
        Raises:
            ValueError: If path doesn't match any valid format
        """
        path = path.strip().rstrip('/')
        
        # Check for hierarchical format: jobs/YYYY/MM/DD/HHmmss
        if path.startswith("jobs/") and len(path.split("/")) == 5:
            parts = path.split("/")
            final_part = parts[-1]
            
            # Validate timestamp part (6 digits)
            if len(final_part) == 6 and final_part.isdigit():
                # Parse hierarchical path
                year, month, day, time_part = parts[1], parts[2], parts[3], parts[4]
                timestamp_str = f"{year}-{month}-{day}_{time_part}"
                return cls(path, timestamp_str, is_hierarchical=True)
        
        # Check for legacy format: YYYY-MM-DD_HHMMSS
        elif re.match(UTC_REGEX_PATTERN_BW_COMPAT, path):
            return cls(path, path, is_hierarchical=False)
        
        raise ValueError(f"Invalid job directory format: {path}")
    
    @classmethod
    def list_all(cls, storage) -> List['JobDir']:
        """
        List all valid job directories from storage.
        
        Args:
            storage: Storage adapter instance
            
        Returns:
            List of JobDir instances, sorted chronologically (oldest first)
        """
        all_dirs = storage.list_directories("")
        job_dirs = []
        
        for dir_name in all_dirs:
            try:
                job_dir = cls.from_path(dir_name)
                job_dirs.append(job_dir)
            except ValueError:
                # Skip invalid directories
                continue
        
        # Sort chronologically (oldest first)
        job_dirs.sort()
        return job_dirs
    
    @classmethod
    def find_latest(cls, storage) -> Optional['JobDir']:
        """
        Find the most recent job directory.
        
        Args:
            storage: Storage adapter instance
            
        Returns:
            JobDir instance for latest job, or None if no jobs found
        """
        job_dirs = cls.list_all(storage)
        return job_dirs[-1] if job_dirs else None
    
    @classmethod
    def group_by_week(cls, job_dirs: List['JobDir']) -> dict[str, List['JobDir']]:
        """
        Group job directories by week key.
        
        Args:
            job_dirs: List of JobDir instances
            
        Returns:
            Dictionary mapping week keys to lists of JobDir instances
        """
        weeks = {}
        for job_dir in job_dirs:
            week_key = job_dir.week_key
            if week_key not in weeks:
                weeks[week_key] = []
            weeks[week_key].append(job_dir)
        return weeks
    
    @property
    def storage_path(self) -> str:
        """Full path for storage operations."""
        return self._storage_path
    
    @property
    def timestamp_str(self) -> str:
        """Timestamp in YYYY-MM-DD_HHMMSS format."""
        return self._timestamp_str
    
    @property
    def datetime(self) -> datetime.datetime:
        """UTC datetime object."""
        return self._datetime
    
    @property
    def week_key(self) -> str:
        """Week key in format YYYY-WNN (e.g., '2025-W22')."""
        return self._week_key
    
    @property
    def is_hierarchical(self) -> bool:
        """True if hierarchical format, False if legacy."""
        return self._is_hierarchical
    
    def __str__(self) -> str:
        """Return storage path for string representation."""
        return self._storage_path
    
    def __repr__(self) -> str:
        """Return detailed representation."""
        format_type = "hierarchical" if self._is_hierarchical else "legacy"
        return f"JobDir('{self._storage_path}', {format_type})"
    
    def __eq__(self, other) -> bool:
        """Equality based on timestamp."""
        if not isinstance(other, JobDir):
            return False
        return self._timestamp_str == other._timestamp_str
    
    def __lt__(self, other) -> bool:
        """Less than comparison for sorting (chronological order)."""
        if not isinstance(other, JobDir):
            return NotImplemented
        return self._timestamp_str < other._timestamp_str
    
    def __hash__(self) -> int:
        """Hash based on timestamp for use in sets/dicts."""
        return hash(self._timestamp_str)