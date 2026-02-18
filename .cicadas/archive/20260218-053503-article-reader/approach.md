# Approach: Article Reader

## Strategy
We will implement this feature in a single partition, as the components (Formatter, Templates, Deployer) are tightly coupled for this specific feature and the scope is small.

## Partitions

### Partition 1: Static Reader Core [COMPLETED]
**Modules**: `presentation/html_formatter.py`, `presentation/deployer.py`, `templates/*.j2`
**Scope**:
-   Create Jinja2 template for article pages.
-   Update Formatter to generate static HTML for each extracted article.
-   Update Weekly Report template to link to these pages.
-   Update Deployer to upload the nested `articles/` directory.

#### Implementation Steps
1.  **Template**: Create `article_template.j2`.
2.  **Formatter**: Implement `generate_article_page` method and integrate into the weekly generation loop.
3.  **Report**: Add "Reader View" links to `weekly_template.j2`.
4.  **Deployer**: Modify `get_files_to_deploy` to include `articles/**/*.html`.

## Sequencing
Single partition, so no complex sequencing required.

## Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| **Storage Bloat** | Generated HTML files are text-only and small (~5-10KB). Storage impact is negligible. |
| **Build Time** | `format_cursor` ensures we only generate pages for *new* runs, preventing full regeneration loops. |
