# Tech Design: Article Reader

## Summary
The Article Reader generates static HTML files for each extracted article JSON during the `format` phase. These files are linked from the main reports and deployed to the `articles/` subdirectory on the web server.

## Architecture
1.  **Formatter**: During `generate_weekly_content`, we iterate through extracted articles.
2.  **Generation**: For each article, `HtmlFormatter` renders `article_template.j2`.
3.  **Storage**: Resulting HTML is saved to `staging/articles/{year}/{month}/{day}/{time}/{site-filename}.html`, mirroring the source job hierarchy.
4.  **Deployment**: `Deployer` uploads the `staging/articles` directory recursively, preserving the nested date tree.

## Data Models
No schema changes. We utilize the existing `article.json` structure:
```json
{
  "title": "String",
  "text": "String (multi-paragraph)",
  "url": "String",
  "metadata": { ... }
}
```

## API Design
N/A - Static Site Generation.

## Components

### `HtmlFormatter` Extensions
-   `generate_article_page(article: Dict, site: str, output_path: str)`:
    -   Loads `article_template.j2`.
    -   Renders with article data.
    -   Writes to disk.
-   **Integration**: Inside `generate_weekly_reports`, loop through `run["extracted"]` -> `stories` and call generation.

### `Deployer` Extensions
-   `get_files_to_deploy(cursor)`:
    -   Current logic only globs `*.html` in root.
    -   **Change**: Now globs `**/*.html` to catch the nested `articles/` hierarchy.
    -   **Optimization**: `upload_file` was updated to automatically create nested remote directories as needed before uploading.

## Security & Performance
-   **XSS Prevention**: `Jinja2` auto-escaping must be enabled (default) to prevent malicious scripts in scraped article text from executing.
-   **Build Performance**: Generating thousands of static files could be slow.
    -   *Mitigation*: The `format_cursor` logic implies we only generate for *new* runs. We must ensure the article generation respects this incremental approach.
