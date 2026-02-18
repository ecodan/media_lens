# Presentation Module

## Purpose
The Presentation module is responsible for the final output of the pipeline: generating static helper files and deploying them to a web server.

## Key Components

### HtmlFormatter (`src.media_lens.presentation.html_formatter`)
The `HtmlFormatter` converts processed data into a user-friendly HTML website.
-   **Templating**: Uses `Jinja2` to render data into HTML.
-   **Incremental Processing**: Tracks a `format_cursor.txt` to only regenerate HTML for new jobs unless `--force-full-format` is used.
-   **Organization**:
    -   Groups jobs by ISO week.
    -   Generates:
        -   `index.html`: Landing page with rolling 7-day view.
        -   `medialens-{week_key}.html`: Static weekly archive pages.
        -   `articles/{year}/{month}/{day}/{time}/{site-filename}.html`: Standalone reader-view article pages.

### Deployer (`src.media_lens.presentation.deployer`)
The `Deployer` handles the transfer of generated assets to the hosting environment.
-   **Method**: `SFTP` upload via `paramiko`.
-   **Recursive Deployment**: `Deployer` scans for `**/*.html` to ensure nested article directories are included.
-   **Auto-Directory Creation**: `upload_file` automatically creates nested remote directory paths on the target server before uploading content.
-   **Fallback**: Supports `IP fallback` if DNS resolution fails for the FTP host.

## Data Flow
1.  **Input**: Interpretation JSON files + processed daily summaries.
2.  **Format**: `HtmlFormatter` reads data -> applies `Jinja2` templates -> saves HTML to `staging/`.
3.  **Deploy**: `Deployer` reads `staging/` -> connects via SFTP -> uploads to remote server.

## Output Structure (`staging/`)
-   `medialens.html` (Index)
-   `medialens-{week_key}.html` (Weekly Archives)
-   `articles/` (Standalone Article Pages)
-   `assets/` (CSS, JS, Images)
