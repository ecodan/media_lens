---
steps_completed: [static-reader-core]
next_section: 'Archive'
---

# PRD: Article Reader

## Problem Statement
Users of the Media Lens weekly reports frequently encounter paywalls when clicking the "Source" links to read the full articles. This friction prevents them from verifying the analysis or reading the primary source material, undermining the tool's value as a media literacy aid.

## Users
-   **Media Researchers**: Need to verify the exact wording and context of the articles analyzed.
-   **General Readers**: Want to consume the news content without subscribing to dozens of different outlets.

## Success Criteria
-   **Availability**: 100% of analyzed articles have a corresponding local "Reader View" link.
-   **Accessibility**: Users can access the full text of an article with a single click from the weekly report.
-   **Performance**: Reader pages load instantly (< 200ms) as they are static HTML.

## Scope

### In Scope
-   Generation of static HTML pages for each extracted article.
-   Integration of "Read Here" links in the `weekly_template.j2`.
-   Updates to `HtmlFormatter` to generate these pages.
-   Updates to `Deployer` to upload the new `articles/` directory.

### Out of Scope
-   Dynamic backend or API for fetching articles on demand.
-   Bypassing paywalls during the *reading* phase (we rely on the text captured during the *harvest* phase).
-   Advanced reader features like highlighting, annotation, or font adjustments (v1 is simple static HTML).

## Requirements

### Functional
1.  **Generate Article Pages**: The system must generate a standalone HTML file for every `article.json` extracted.
2.  **Display Content**: These pages must display the Title, Author, Date, Original URL, and the full Body Text.
3.  **Link Integration**: The weekly report list items must include a secondary link labeled "Reader View" next to the original title link.
4.  **Navigation**: The Reader View must include a "Back" button or link to return to the report.

### Non-Functional
1.  **Readability**: The Reader View must use high-readability typography (system fonts, optimal line length, sufficient contrast).
2.  **Responsiveness**: The view must work well on mobile devices.
3.  **Storage Efficiency**: Generated HTML files should be minimal in size (no heavy frameworks).

## Open Questions
-   **Copyright**: Is hosting full text problematic? *Mitigation: This is currently a personal/research tool. Access control could be added later if deployed publicly.*
