# Article Reader Design

## Goal
Enable users to read the full text of articles directly within the Media Lens application, bypassing paywalls and ensuring content availability.

## Approach
Implement a "Reader View" by generating static HTML pages for each extracted article. These pages will be hosted alongside the main reports and linked from the weekly/daily summaries.

## Components

### 1. HtmlFormatter Update (`src.media_lens.presentation.html_formatter`)
-   **New Method**: `generate_article_page(article_data, template_path)`
-   **Integration**: Call this method for every article in the weekly data during formatting.
-   **Output**: `staging/articles/{site}/{filename}.html` to avoid cluttering the root.

### 2. Template (`config/templates/article_template.j2`)
-   **Layout**: Clean, distraction-free reading experience.
-   **Content**: Title, Author/Date (if available), Original Link, Full Text (formatted with paragraphs).
-   **Navigation**: "Back to Report" link.

### 3. Deployer Update (`src.media_lens.presentation.deployer`)
-   **Recursive Upload**: Update `get_files_to_deploy` to include the `articles/` subdirectory.
-   **Path Handling**: Ensure relative links between reports and articles work correctly in the deployed environment.

### 4. Weekly Report Update (`config/templates/weekly_template.j2`)
-   **Links**: Add a "Read Here" or "Reader View" link next to the original "Source" link for each article.

## Pros/Cons
-   **Pros**:
    -   Bypasses paywalls (using already extracted text).
    -   Fast loading (static HTML).
    -   No external dependencies or dynamic backend required.
    -   Zero additional cost.
-   **Cons**:
    -   Increases build time and storage usage (one file per article).
    -   Potential copyright considerations for public hosting (mitigated by personal use focus).
