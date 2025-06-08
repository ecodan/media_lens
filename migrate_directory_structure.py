#!/usr/bin/env python3
"""
Migration script to convert existing flat directory structure to new hierarchical structure.

This script:
1. Discovers all existing flat timestamp directories (YYYY-MM-DD_HHMMSS format)
2. Moves them to the new hierarchical structure (jobs/YYYY/MM/DD/HHmmss/)
3. Moves interpreted files to intermediate/ directory
4. Moves HTML files to staging/ directory
5. Works with both local and cloud storage via the storage adapter

Usage:
    python migrate_directory_structure.py [--dry-run] [--backup]
    
Options:
    --dry-run: Show what would be migrated without making changes
    --backup: Create backup of original structure before migration
"""

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import List, Dict, Set

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.media_lens.common import LOGGER_NAME, create_logger, UTC_REGEX_PATTERN_BW_COMPAT, get_utc_datetime_from_timestamp
from src.media_lens.storage import shared_storage
from src.media_lens.storage_adapter import StorageAdapter

logger = logging.getLogger(LOGGER_NAME)


class DirectoryMigrator:
    """Handles migration from flat to hierarchical directory structure."""
    
    def __init__(self, storage: StorageAdapter, dry_run: bool = False, backup: bool = False, delete_old: bool = False):
        self.storage = storage
        self.dry_run = dry_run
        self.backup = backup
        self.delete_old = delete_old
        self.migration_stats = {
            "job_dirs_migrated": 0,
            "interpreted_files_moved": 0,
            "html_files_moved": 0,
            "files_deleted": 0,
            "dirs_deleted": 0,
            "errors": 0
        }
    
    def discover_legacy_directories(self) -> List[str]:
        """Find all directories that match the legacy flat timestamp pattern."""
        logger.info("Discovering legacy flat directories...")
        
        all_dirs = self.storage.list_directories("")
        legacy_dirs = []
        
        for dir_name in all_dirs:
            # Check if this is a legacy flat directory (not already hierarchical)
            if re.match(r'^\d{4}-\d{2}-\d{2}_\d{6}$', dir_name):
                legacy_dirs.append(dir_name)
        
        logger.info(f"Found {len(legacy_dirs)} legacy directories to migrate")
        return sorted(legacy_dirs)
    
    def discover_loose_files(self) -> Dict[str, List[str]]:
        """Find interpreted.json and HTML files in the root that should be organized."""
        logger.info("Discovering loose files to organize...")
        
        all_files = self.storage.list_files("")
        loose_files = {
            "interpreted": [],
            "html": [],
            "weekly_interpreted": []
        }
        
        for file_path in all_files:
            # Skip files that are already in subdirectories
            if "/" in file_path:
                continue
                
            # Find interpreted files
            if file_path.endswith("-interpreted.json") and not file_path.startswith("weekly-"):
                loose_files["interpreted"].append(file_path)
            elif file_path.startswith("weekly-") and file_path.endswith("-interpreted.json"):
                loose_files["weekly_interpreted"].append(file_path)
            # Find HTML files
            elif file_path.endswith(".html") and file_path.startswith("medialens"):
                loose_files["html"].append(file_path)
        
        total_files = sum(len(files) for files in loose_files.values())
        logger.info(f"Found {total_files} loose files to organize")
        return loose_files
    
    def create_backup(self, legacy_dirs: List[str], loose_files: Dict[str, List[str]]) -> None:
        """Create a backup of the current structure."""
        if not self.backup:
            return
            
        logger.info("Creating backup of current structure...")
        backup_dir = "migration_backup"
        
        try:
            self.storage.create_directory(backup_dir)
            
            # Backup legacy directories
            for legacy_dir in legacy_dirs:
                backup_path = f"{backup_dir}/{legacy_dir}"
                self.storage.create_directory(backup_path)
                
                # Copy all files from legacy directory
                files = self.storage.list_files(legacy_dir)
                for file_path in files:
                    if file_path.startswith(legacy_dir + "/"):
                        relative_path = file_path[len(legacy_dir) + 1:]
                        backup_file_path = f"{backup_path}/{relative_path}"
                        
                        try:
                            content = self.storage.read_binary(file_path)
                            self.storage.write_binary(backup_file_path, content)
                        except Exception as e:
                            logger.warning(f"Failed to backup file {file_path}: {e}")
            
            # Backup loose files
            for category, files in loose_files.items():
                category_backup_dir = f"{backup_dir}/loose_{category}"
                self.storage.create_directory(category_backup_dir)
                
                for file_path in files:
                    backup_file_path = f"{category_backup_dir}/{file_path}"
                    try:
                        content = self.storage.read_binary(file_path)
                        self.storage.write_binary(backup_file_path, content)
                    except Exception as e:
                        logger.warning(f"Failed to backup file {file_path}: {e}")
            
            logger.info(f"Backup created in {backup_dir}")
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise
    
    def migrate_job_directory(self, legacy_dir: str) -> bool:
        """Migrate a single legacy job directory to hierarchical structure."""
        try:
            # Parse the timestamp to get the hierarchical path
            job_datetime = get_utc_datetime_from_timestamp(legacy_dir)
            new_job_dir = self.storage.get_job_directory(legacy_dir)
            
            logger.info(f"Migrating {legacy_dir} -> {new_job_dir}")
            
            if self.dry_run:
                return True
            
            # Create the new hierarchical directory
            self.storage.create_directory(new_job_dir)
            
            # Move all files from legacy directory to new structure
            files = self.storage.list_files(legacy_dir)
            files_moved = 0
            
            for file_path in files:
                if file_path.startswith(legacy_dir + "/"):
                    relative_path = file_path[len(legacy_dir) + 1:]
                    new_file_path = f"{new_job_dir}/{relative_path}"
                    
                    try:
                        # Read content from old location
                        content = self.storage.read_binary(file_path)
                        
                        # Write to new location
                        self.storage.write_binary(new_file_path, content)
                        files_moved += 1
                        
                        logger.debug(f"Moved file: {file_path} -> {new_file_path}")
                        
                    except Exception as e:
                        logger.error(f"Failed to move file {file_path}: {e}")
                        self.migration_stats["errors"] += 1
                        return False
            
            logger.info(f"Moved {files_moved} files from {legacy_dir}")
            self.migration_stats["job_dirs_migrated"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate directory {legacy_dir}: {e}")
            self.migration_stats["errors"] += 1
            return False
    
    def organize_interpreted_files(self, interpreted_files: List[str]) -> None:
        """Move interpreted files to appropriate intermediate directories."""
        logger.info(f"Organizing {len(interpreted_files)} interpreted files...")
        
        for file_path in interpreted_files:
            try:
                # Try to extract timestamp from filename (site-interpreted.json pattern)
                # We need to match this with existing job directories
                site_name = file_path.replace("-interpreted.json", "")
                
                # Find the most recent job directory that contains this site
                job_dir = self._find_job_for_interpreted_file(site_name, file_path)
                
                if job_dir:
                    # Extract timestamp for intermediate directory organization
                    if job_dir.startswith("jobs/"):
                        job_timestamp = self.storage.directory_manager.parse_job_timestamp(job_dir)
                    else:
                        job_timestamp = job_dir
                    
                    intermediate_dir = self.storage.get_intermediate_directory(job_timestamp)
                    new_file_path = f"{intermediate_dir}/{file_path}"
                    
                    logger.info(f"Moving interpreted file: {file_path} -> {new_file_path}")
                    
                    if not self.dry_run:
                        self.storage.create_directory(intermediate_dir)
                        content = self.storage.read_binary(file_path)
                        self.storage.write_binary(new_file_path, content)
                    
                    self.migration_stats["interpreted_files_moved"] += 1
                else:
                    logger.warning(f"Could not find matching job directory for {file_path}")
                    
            except Exception as e:
                logger.error(f"Failed to organize interpreted file {file_path}: {e}")
                self.migration_stats["errors"] += 1
    
    def organize_weekly_files(self, weekly_files: List[str]) -> None:
        """Move weekly interpreted files to intermediate directory."""
        logger.info(f"Organizing {len(weekly_files)} weekly interpreted files...")
        
        intermediate_dir = self.storage.get_intermediate_directory()
        
        for file_path in weekly_files:
            try:
                new_file_path = f"{intermediate_dir}/{file_path}"
                
                logger.info(f"Moving weekly file: {file_path} -> {new_file_path}")
                
                if not self.dry_run:
                    self.storage.create_directory(intermediate_dir)
                    content = self.storage.read_binary(file_path)
                    self.storage.write_binary(new_file_path, content)
                
                self.migration_stats["interpreted_files_moved"] += 1
                
            except Exception as e:
                logger.error(f"Failed to organize weekly file {file_path}: {e}")
                self.migration_stats["errors"] += 1
    
    def organize_html_files(self, html_files: List[str]) -> None:
        """Move HTML files to staging directory."""
        logger.info(f"Organizing {len(html_files)} HTML files...")
        
        staging_dir = self.storage.get_staging_directory()
        
        for file_path in html_files:
            try:
                new_file_path = f"{staging_dir}/{file_path}"
                
                logger.info(f"Moving HTML file: {file_path} -> {new_file_path}")
                
                if not self.dry_run:
                    self.storage.create_directory(staging_dir)
                    content = self.storage.read_binary(file_path)
                    self.storage.write_binary(new_file_path, content)
                
                self.migration_stats["html_files_moved"] += 1
                
            except Exception as e:
                logger.error(f"Failed to organize HTML file {file_path}: {e}")
                self.migration_stats["errors"] += 1
    
    def _find_job_for_interpreted_file(self, site_name: str, file_path: str) -> str:
        """Find the most appropriate job directory for an interpreted file."""
        # Look for job directories that contain files for this site
        all_dirs = self.storage.list_directories("")
        
        matching_jobs = []
        
        for dir_name in all_dirs:
            # Check both legacy and new hierarchical directories
            if (re.match(r'^\d{4}-\d{2}-\d{2}_\d{6}$', dir_name) or 
                (dir_name.startswith("jobs/") and len(dir_name.split("/")) >= 5)):
                
                # Check if this job directory has files for this site
                try:
                    files = self.storage.list_files(dir_name)
                    site_files = [f for f in files if site_name in f and "clean-article" in f]
                    
                    if site_files:
                        # Parse timestamp for sorting
                        if dir_name.startswith("jobs/"):
                            timestamp = self.storage.directory_manager.parse_job_timestamp(dir_name)
                            job_datetime = get_utc_datetime_from_timestamp(timestamp)
                        else:
                            job_datetime = get_utc_datetime_from_timestamp(dir_name)
                        
                        matching_jobs.append((dir_name, job_datetime))
                        
                except Exception as e:
                    logger.debug(f"Could not check job directory {dir_name}: {e}")
        
        if matching_jobs:
            # Return the most recent job directory
            matching_jobs.sort(key=lambda x: x[1], reverse=True)
            return matching_jobs[0][0]
        
        return None
    
    def cleanup_legacy_structure(self, legacy_dirs: List[str], loose_files: Dict[str, List[str]]) -> None:
        """Remove the old directory structure after successful migration."""
        if self.dry_run:
            logger.info("Would clean up legacy directories and files (dry run)")
            return
        
        if not self.delete_old:
            logger.info("Skipping cleanup - delete_old=False")
            return
        
        logger.info("Cleaning up legacy structure...")
        
        # Remove loose files first
        all_loose_files = []
        for files in loose_files.values():
            all_loose_files.extend(files)
        
        for file_path in all_loose_files:
            try:
                if self.storage.delete_file(file_path):
                    logger.info(f"Deleted loose file: {file_path}")
                    self.migration_stats["files_deleted"] += 1
                else:
                    logger.warning(f"Could not delete loose file: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting loose file {file_path}: {e}")
                self.migration_stats["errors"] += 1
        
        # Remove legacy directories (should be empty after moving files)
        for legacy_dir in legacy_dirs:
            try:
                if self.storage.delete_directory(legacy_dir, recursive=True):
                    logger.info(f"Deleted legacy directory: {legacy_dir}")
                    self.migration_stats["dirs_deleted"] += 1
                else:
                    logger.warning(f"Could not delete legacy directory: {legacy_dir}")
            except Exception as e:
                logger.error(f"Error deleting legacy directory {legacy_dir}: {e}")
                self.migration_stats["errors"] += 1
    
    def migrate(self) -> bool:
        """Perform the complete migration."""
        logger.info(f"Starting migration (dry_run={self.dry_run}, backup={self.backup})")
        
        try:
            # Discover what needs to be migrated
            legacy_dirs = self.discover_legacy_directories()
            loose_files = self.discover_loose_files()
            
            if not legacy_dirs and not any(loose_files.values()):
                logger.info("No legacy structure found - nothing to migrate")
                return True
            
            # Create backup if requested
            if self.backup:
                self.create_backup(legacy_dirs, loose_files)
            
            # Migrate job directories
            for legacy_dir in legacy_dirs:
                if not self.migrate_job_directory(legacy_dir):
                    logger.error(f"Failed to migrate {legacy_dir}, stopping migration")
                    return False
            
            # Organize loose files
            self.organize_interpreted_files(loose_files["interpreted"])
            self.organize_weekly_files(loose_files["weekly_interpreted"])
            self.organize_html_files(loose_files["html"])
            
            # Clean up old structure (optional)
            if not self.dry_run:
                self.cleanup_legacy_structure(legacy_dirs, loose_files)
            
            # Report results
            self.print_migration_summary()
            
            return self.migration_stats["errors"] == 0
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def print_migration_summary(self) -> None:
        """Print a summary of the migration results."""
        stats = self.migration_stats
        action = "Would migrate" if self.dry_run else "Migrated"
        delete_action = "Would delete" if self.dry_run else "Deleted"
        
        logger.info("="*50)
        logger.info("MIGRATION SUMMARY")
        logger.info("="*50)
        logger.info(f"{action} {stats['job_dirs_migrated']} job directories")
        logger.info(f"{action} {stats['interpreted_files_moved']} interpreted files")
        logger.info(f"{action} {stats['html_files_moved']} HTML files")
        
        if self.delete_old or self.dry_run:
            logger.info(f"{delete_action} {stats['files_deleted']} loose files")
            logger.info(f"{delete_action} {stats['dirs_deleted']} legacy directories")
        
        if stats["errors"] > 0:
            logger.error(f"Encountered {stats['errors']} errors during migration")
        else:
            logger.info("Migration completed successfully!")
        
        if self.dry_run:
            logger.info("This was a dry run - no changes were made")
        elif not self.delete_old:
            logger.info("Legacy files were not deleted (use --delete-old to remove them)")
        logger.info("="*50)


def main():
    parser = argparse.ArgumentParser(description='Migrate media-lens directory structure')
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Show what would be migrated without making changes'
    )
    parser.add_argument(
        '--backup',
        action='store_true', 
        help='Create backup of original structure before migration'
    )
    parser.add_argument(
        '--delete-old',
        action='store_true',
        help='Delete original files and directories after successful migration'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level'
    )
    
    args = parser.parse_args()
    
    # Set up logging
    create_logger(LOGGER_NAME)
    logger.setLevel(getattr(logging, args.log_level))
    
    # Load environment
    import dotenv
    dotenv.load_dotenv()
    
    logger.info("Starting directory structure migration")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Backup: {args.backup}")
    logger.info(f"Delete old: {args.delete_old}")
    
    # Validate arguments
    if args.delete_old and not args.backup and not args.dry_run:
        logger.warning("--delete-old specified without --backup. This permanently removes old files!")
        response = input("Are you sure you want to proceed without backup? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Aborting migration")
            sys.exit(0)
    
    # Initialize migrator
    migrator = DirectoryMigrator(
        storage=shared_storage,
        dry_run=args.dry_run,
        backup=args.backup,
        delete_old=args.delete_old
    )
    
    # Perform migration
    success = migrator.migrate()
    
    if success:
        logger.info("Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()