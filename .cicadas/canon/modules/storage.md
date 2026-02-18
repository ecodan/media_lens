# Storage Module

## Purpose
The Storage module provides an abstraction layer for all file I/O, allowing the application to run seamlessly on a local filesystem or in a cloud environment (GCS).

## Key Components

### StorageAdapter (`src.media_lens.storage_adapter`)
The `StorageAdapter` is a singleton that implements the file I/O interface.
-   **Abstraction**: Provides methods like `read_text`, `write_text`, `read_json`, `write_json`, `list_files`, `file_exists`.
-   **Backends**:
    -   **Local**: Uses Python's standard `open()` and `os` module. Path is defined by `LOCAL_STORAGE_PATH` (default: `./working`).
    -   **Cloud**: Uses `google-cloud-storage`. Bucket is defined by `GCP_STORAGE_BUCKET`.
-   **Configuration**: Supports `USE_CLOUD_STORAGE` environment variable to switch backends.
-   **Authentication**: Handles GCP credentials via `GOOGLE_APPLICATION_CREDENTIALS` or Workload Identity.

### Directory Structure
The application uses a strict directory hierarchy for job artifacts:
-   `jobs/YYYY/MM/DD/HHMMSS/`: Container for a single run.
    -   `site.html`: Raw HTML.
    -   `site-clean.html`: Cleaned HTML.
    -   `site-extracted.json`: Headlines and metadata.
    -   `site-article-N.json`: Individual article text.
    -   `site-interpreted.json`: LLM analysis.
    -   `daily_news.txt`: Daily summary.
-   `staging/`: Output directory for generated HTML.
-   `intermediate/`: Global accumulation of data (e.g., weekly summaries).

## Data Flow
All modules interacting with the filesystem (`Harvester`, `Extractor`, `Interpreter`, `Formatter`, `Deployer`) do so exclusively through the `StorageAdapter` instance. This ensures portability.
