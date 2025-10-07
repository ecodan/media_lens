"""
Directory management for media lens application.

Provides centralized directory path generation and date handling for:
1. Job directories: YYYY/MM/DD/HHmmss/ for chronological organization
2. Intermediate data: intermediate/ for processed data files
3. Staging: staging/ for website-ready files
"""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Union

from src.media_lens.common import LOGGER_NAME, UTC_DATE_PATTERN_BW_COMPAT

logger = logging.getLogger(LOGGER_NAME)


class DirectoryManager:
    """Manages directory structure for media lens application."""

    def __init__(self, base_path: Union[str, Path] = ""):
        """
        Initialize the directory manager.
        
        Args:
            base_path: Base path for all directories (e.g., 'working' or cloud storage prefix)
        """
        self.base_path = Path(base_path) if base_path else Path("")

    def get_job_dir(self, timestamp: Optional[str] = None) -> str:
        """
        Get a job directory path in YYYY/MM/DD/HHmmss format.
        
        Args:
            timestamp: Optional timestamp string. If None, uses current time.
            
        Returns:
            Job directory path relative to base_path
        """
        if timestamp is None:
            dt = datetime.now(timezone.utc)
            timestamp = dt.strftime(UTC_DATE_PATTERN_BW_COMPAT)
        else:
            # Parse existing timestamp to get datetime
            dt = datetime.strptime(timestamp, UTC_DATE_PATTERN_BW_COMPAT)
            dt = dt.replace(tzinfo=timezone.utc)

        # Format: YYYY/MM/DD/HHmmss
        year = dt.strftime("%Y")
        month = dt.strftime("%m")
        day = dt.strftime("%d")
        time_part = dt.strftime("%H%M%S")

        job_path = self.base_path / "jobs" / year / month / day / time_part
        return str(job_path)

    def get_intermediate_dir(self, subdir: str = "") -> str:
        """
        Get intermediate data directory path.
        
        Args:
            subdir: Optional subdirectory within intermediate
            
        Returns:
            Intermediate directory path relative to base_path
        """
        if subdir:
            path = self.base_path / "intermediate" / subdir
        else:
            path = self.base_path / "intermediate"
        return str(path)

    def get_staging_dir(self, subdir: str = "") -> str:
        """
        Get staging directory path for website-ready files.
        
        Args:
            subdir: Optional subdirectory within staging
            
        Returns:
            Staging directory path relative to base_path
        """
        if subdir:
            path = self.base_path / "staging" / subdir
        else:
            path = self.base_path / "staging"
        return str(path)

    def parse_job_timestamp(self, job_dir: str) -> str:
        """
        Extract timestamp from job directory path.
        
        Args:
            job_dir: Job directory path
            
        Returns:
            Timestamp string in UTC_DATE_PATTERN_BW_COMPAT format
        """
        # Extract components from path like "jobs/2025/01/15/143022"
        path = Path(job_dir)
        parts = path.parts

        # Find the timestamp parts
        if len(parts) >= 4 and "jobs" in parts:
            jobs_idx = parts.index("jobs")
            if jobs_idx + 4 < len(parts):
                year = parts[jobs_idx + 1]
                month = parts[jobs_idx + 2]
                day = parts[jobs_idx + 3]
                time_part = parts[jobs_idx + 4]

                # Convert to timestamp format YYYY-MM-DD_HHMMSS
                return f"{year}-{month}-{day}_{time_part}"

        raise ValueError(f"Could not parse timestamp from job directory: {job_dir}")

    def get_jobs_in_date_range(self, start_date: str, end_date: str, storage_adapter) -> List[str]:
        """
        Get all job directories within a date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format  
            storage_adapter: Storage adapter to list directories
            
        Returns:
            List of job directory paths within the date range
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)

        job_dirs = []
        jobs_base = str(self.base_path / "jobs")

        # Get all directories under jobs/
        try:
            all_dirs = storage_adapter.list_directories(jobs_base)

            for dir_path in all_dirs:
                try:
                    timestamp = self.parse_job_timestamp(dir_path)
                    job_dt = datetime.strptime(timestamp, UTC_DATE_PATTERN_BW_COMPAT)
                    job_dt = job_dt.replace(tzinfo=timezone.utc)

                    if start_dt <= job_dt <= end_dt:
                        job_dirs.append(dir_path)
                except ValueError:
                    # Skip directories that don't match expected format
                    continue

        except Exception as e:
            logger.warning(f"Could not list job directories: {e}")

        return sorted(job_dirs)

    def get_date_range_boundaries(self, start_date: str, end_date: str) -> Tuple[datetime, datetime]:
        """
        Parse date range strings and handle month/year boundaries properly.
        
        Args:
            start_date: Start date string in YYYY-MM-DD format
            end_date: End date string in YYYY-MM-DD format
            
        Returns:
            Tuple of (start_datetime, end_datetime) in UTC
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
        )
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc
        )

        return start_dt, end_dt

    def get_jobs_by_pattern(self, pattern: str, storage_adapter) -> List[str]:
        """
        Get job directories matching a pattern.
        
        Args:
            pattern: Pattern to match (e.g., "2025/01/*" for January 2025)
            storage_adapter: Storage adapter to search
            
        Returns:
            List of matching job directory paths
        """
        jobs_base = str(self.base_path / "jobs")
        search_pattern = f"{jobs_base}/{pattern}"

        try:
            return storage_adapter.get_files_by_pattern("", search_pattern)
        except Exception as e:
            logger.warning(f"Could not search for job pattern {pattern}: {e}")
            return []
