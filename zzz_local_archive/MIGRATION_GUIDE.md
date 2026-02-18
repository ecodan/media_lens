# Directory Structure Migration Guide

This guide explains how to migrate your existing media-lens working directory from the old flat structure to the new hierarchical structure.

## Overview

The migration script converts:

**Old Structure (Flat)**:
```
working/
├── 2025-06-01_120000/          # Job directories
│   ├── www.cnn.com.html
│   ├── www.cnn.com-clean.html
│   └── www.cnn.com-clean-article-*.json
├── www.cnn.com-interpreted.json # Interpreted files (loose)
├── weekly-2025-W23-interpreted.json # Weekly files (loose)
└── medialens.html               # HTML files (loose)
```

**New Structure (Hierarchical)**:
```
working/
├── jobs/                        # Organized job directories
│   └── 2025/06/01/120000/      # Year/Month/Day/Time
│       ├── www.cnn.com.html
│       ├── www.cnn.com-clean.html
│       └── www.cnn.com-clean-article-*.json
├── intermediate/                # Processed data
│   ├── 2025-06-01_120000/      # Per-job interpreted files
│   │   └── www.cnn.com-interpreted.json
│   └── weekly-2025-W23-interpreted.json
└── staging/                     # Website-ready files
    ├── medialens.html
    └── medialens-2025-W23.html
```

## Migration Script

### Basic Usage

```bash
# Dry run (see what would be migrated without making changes)
python migrate_directory_structure.py --dry-run

# Safe migration with backup (keeps old files)
python migrate_directory_structure.py --backup

# Complete migration with backup and cleanup (recommended)
python migrate_directory_structure.py --backup --delete-old

# Quick migration without backup or cleanup (faster, but less safe)
python migrate_directory_structure.py
```

### Options

- `--dry-run`: Show what would be migrated without making changes
- `--backup`: Create backup of original structure before migration
- `--delete-old`: Delete original files and directories after successful migration
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR)

### Examples

```bash
# Safe migration with detailed logging and cleanup
python migrate_directory_structure.py --backup --delete-old --log-level DEBUG

# Quick test run to see what would change
python migrate_directory_structure.py --dry-run --log-level INFO

# Production migration (recommended)
python migrate_directory_structure.py --backup --delete-old

# Migration without cleanup (keeps old files alongside new structure)
python migrate_directory_structure.py --backup
```

## What the Script Does

### 1. Discovery Phase
- Finds all legacy flat directories matching `YYYY-MM-DD_HHMMSS` pattern
- Identifies loose interpreted files (`*-interpreted.json`)
- Identifies loose weekly files (`weekly-*-interpreted.json`)  
- Identifies loose HTML files (`medialens*.html`)

### 2. Backup Phase (if --backup)
- Creates `migration_backup/` directory
- Copies all legacy directories and loose files to backup

### 3. Migration Phase
- **Job Directories**: Converts `2025-06-01_120000` → `jobs/2025/06/01/120000`
- **Interpreted Files**: Moves to `intermediate/2025-06-01_120000/`
- **Weekly Files**: Moves to `intermediate/`
- **HTML Files**: Moves to `staging/`

### 4. Cleanup Phase (if --delete-old)
- Deletes loose files from root directory
- Recursively deletes legacy job directories and all their contents
- Provides confirmation and safety checks

## Cloud Storage Support

The script works with both local and cloud storage automatically:

```bash
# Local storage
export USE_CLOUD_STORAGE=false
export LOCAL_STORAGE_PATH=./working
python migrate_directory_structure.py --backup

# Cloud storage  
export USE_CLOUD_STORAGE=true
export GCP_STORAGE_BUCKET=your-bucket-name
python migrate_directory_structure.py --backup --delete-old
```

## Pre-Migration Checklist

1. **Backup your data** (the script can do this with `--backup`)
2. **Test with dry run** first: `python migrate_directory_structure.py --dry-run`
3. **Stop any running media-lens processes**
4. **Ensure sufficient storage space** (migration temporarily doubles space usage if not using `--delete-old`)
5. **Set appropriate environment variables** for your storage type
6. **Decide on cleanup strategy**: Use `--delete-old` for complete migration or keep old files for safety

## Post-Migration Verification

After migration, verify the new structure:

```bash
# Test the new directory structure
python -c "
from src.media_lens.storage import shared_storage
print('Job dirs:', shared_storage.list_directories('jobs'))
print('Intermediate:', shared_storage.list_files('intermediate'))  
print('Staging:', shared_storage.list_files('staging'))
"
```

## Rollback

If you need to rollback (and used `--backup`):

1. Stop media-lens processes
2. Delete the new hierarchical directories:
   - `jobs/`
   - `intermediate/`
   - `staging/`
3. Restore from `migration_backup/`:
   ```bash
   # Manual rollback example (adapt for your storage)
   cp -r migration_backup/2025-* ./
   cp migration_backup/loose_*/* ./
   ```

## Troubleshooting

### Common Issues

**"No legacy structure found"**
- This is normal if you're already using the new structure
- Or if your working directory is empty

**"Failed to find matching job directory"**
- Some interpreted files couldn't be matched to job directories
- They'll be placed in the most recent job's intermediate directory

**"--delete-old specified without --backup"**
- Safety warning when using deletion without backup
- Type 'yes' to confirm or use `--backup` for safety

**Storage connection errors**
- Check your environment variables (`USE_CLOUD_STORAGE`, `GCP_STORAGE_BUCKET`, etc.)
- Verify cloud storage credentials if using cloud storage

**Permission errors during deletion**
- Ensure the storage adapter has delete permissions
- For cloud storage, verify the service account has storage.objects.delete permissions

### Getting Help

Run with verbose logging to see detailed progress:
```bash
python migrate_directory_structure.py --dry-run --log-level DEBUG
```

Check the migration summary for statistics on what was processed.

## Performance Notes

- **Local Storage**: Very fast, limited by disk I/O
- **Cloud Storage**: Slower due to network transfer, but works with large datasets
- **Backup Creation**: Doubles the time and storage space temporarily
- **File Deletion**: Fast for local storage, slower for cloud storage due to API calls
- **Large Datasets**: Consider running during off-peak hours
- **Storage Space**: Using `--delete-old` reduces final storage usage but requires more temporary space during migration

## Integration

After successful migration, the new directory structure is automatically used by:

- ✅ Harvester (creates hierarchical job directories)
- ✅ Runner (finds jobs in hierarchical structure) 
- ✅ Interpreter (stores intermediate files correctly)
- ✅ HTML Formatter (outputs to staging directory)
- ✅ Deployer (reads from staging directory)
- ✅ Auditor (works with both old and new structures)

No code changes needed - everything works automatically!