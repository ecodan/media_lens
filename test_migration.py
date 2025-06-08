#!/usr/bin/env python3
"""
Test script to verify the migration functionality works correctly.
Creates sample legacy data and tests the migration process.
"""

import json
import sys
import tempfile
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.media_lens.common import create_logger, LOGGER_NAME
from src.media_lens.storage_adapter import StorageAdapter
from migrate_directory_structure import DirectoryMigrator

def create_test_data(storage: StorageAdapter) -> None:
    """Create sample legacy directory structure for testing."""
    print("Creating test legacy data...")
    
    # Create legacy job directories
    legacy_dirs = [
        "2025-06-01_120000",
        "2025-06-02_130000", 
        "2025-06-03_140000"
    ]
    
    sites = ["www.test1.com", "www.test2.com"]
    
    for legacy_dir in legacy_dirs:
        storage.create_directory(legacy_dir)
        
        for site in sites:
            # Create sample files
            storage.write_text(f"{legacy_dir}/{site}.html", f"<html>Raw content for {site}</html>")
            storage.write_text(f"{legacy_dir}/{site}-clean.html", f"<html>Clean content for {site}</html>")
            
            # Create article files
            for i in range(3):
                article = {
                    "title": f"Test Article {i}",
                    "text": f"Test content for article {i} from {site}",
                    "site": site,
                    "position": i
                }
                storage.write_json(f"{legacy_dir}/{site}-clean-article-{i}.json", article)
    
    # Create loose interpreted files
    for site in sites:
        interpretation = [
            {"question": f"What is happening at {site}?", "answer": f"Test interpretation for {site}"}
        ]
        storage.write_json(f"{site}-interpreted.json", interpretation)
    
    # Create weekly interpreted files
    weekly_interpretation = [
        {"question": "What happened this week?", "answer": "Test weekly interpretation"}
    ]
    storage.write_json("weekly-2025-W23-interpreted.json", weekly_interpretation)
    
    # Create HTML files
    storage.write_text("medialens.html", "<html>Main index page</html>")
    storage.write_text("medialens-2025-W23.html", "<html>Weekly page</html>")
    
    print("Test data created successfully")

def verify_migration(storage: StorageAdapter) -> bool:
    """Verify that the migration worked correctly."""
    print("Verifying migration results...")
    
    success = True
    
    # Check that hierarchical job directories were created
    expected_job_dirs = [
        "jobs/2025/06/01/120000",
        "jobs/2025/06/02/130000",
        "jobs/2025/06/03/140000"
    ]
    
    for job_dir in expected_job_dirs:
        if not storage.file_exists(f"{job_dir}/www.test1.com.html"):
            print(f"ERROR: Missing file in {job_dir}")
            success = False
        else:
            print(f"✓ Found migrated job directory: {job_dir}")
    
    # Check intermediate directory
    intermediate_dir = storage.get_intermediate_directory()
    if storage.file_exists(f"{intermediate_dir}/weekly-2025-W23-interpreted.json"):
        print("✓ Found weekly interpreted file in intermediate directory")
    else:
        print("ERROR: Missing weekly interpreted file")
        success = False
    
    # Check staging directory
    staging_dir = storage.get_staging_directory()
    if storage.file_exists(f"{staging_dir}/medialens.html"):
        print("✓ Found HTML file in staging directory")
    else:
        print("ERROR: Missing HTML file in staging")
        success = False
    
    # Check that old files were deleted
    legacy_dirs_deleted = [
        "2025-06-01_120000",
        "2025-06-02_130000", 
        "2025-06-03_140000"
    ]
    
    for legacy_dir in legacy_dirs_deleted:
        if not storage.file_exists(f"{legacy_dir}/www.test1.com.html"):
            print(f"✓ Legacy directory {legacy_dir} was deleted")
        else:
            print(f"ERROR: Legacy directory {legacy_dir} still exists")
            success = False
    
    # Check that loose files were deleted
    loose_files = ["www.test1.com-interpreted.json", "medialens.html", "weekly-2025-W23-interpreted.json"]
    for loose_file in loose_files:
        if not storage.file_exists(loose_file):
            print(f"✓ Loose file {loose_file} was deleted")
        else:
            print(f"ERROR: Loose file {loose_file} still exists")
            success = False
    
    return success

def main():
    # Set up logging
    create_logger(LOGGER_NAME)
    
    # Use a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using temporary directory: {temp_dir}")
        
        # Override environment for local testing
        import os
        os.environ['USE_CLOUD_STORAGE'] = 'false'
        os.environ['LOCAL_STORAGE_PATH'] = temp_dir
        
        # Create fresh storage adapter for testing
        storage = StorageAdapter()
        
        # Reset singleton to use new path
        StorageAdapter.reset_instance()
        storage = StorageAdapter()
        
        try:
            # Create test data
            create_test_data(storage)
            
            # Test dry run first
            print("\n" + "="*50)
            print("TESTING DRY RUN")
            print("="*50)
            migrator = DirectoryMigrator(storage, dry_run=True, backup=False)
            if not migrator.migrate():
                print("ERROR: Dry run failed")
                return False
            
            # Test actual migration
            print("\n" + "="*50)
            print("TESTING ACTUAL MIGRATION")
            print("="*50)
            migrator = DirectoryMigrator(storage, dry_run=False, backup=True, delete_old=True)
            if not migrator.migrate():
                print("ERROR: Migration failed")
                return False
            
            # Verify results
            print("\n" + "="*50)
            print("VERIFYING RESULTS")
            print("="*50)
            if verify_migration(storage):
                print("\n✅ Migration test PASSED!")
                return True
            else:
                print("\n❌ Migration test FAILED!")
                return False
                
        except Exception as e:
            print(f"Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)