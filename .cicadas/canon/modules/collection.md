# Collection Module

## Purpose
The Collection module is responsible for the "Harvest" phase of the pipeline: acquiring raw content from the web and normalizing it for analysis.

## Key Components

### Harvester (`src.media_lens.collection.harvester`)
The `Harvester` orchestrates the entire collection process.
-   **Sequential Workflow**: It runs a two-phase process: `Scrape` -> `Clean`.
-   **Method**: `harvest(sites, browser_type)`
-   **Output**: Creates a timestamped job directory (e.g., `jobs/2023/10/27/100000`) containing raw `.html` files and cleaned `.html` files.

### Scraper (`src.media_lens.collection.scraper`)
The `WebpageScraper` handles the complexities of fetching modern web pages.
-   **Technology**: Uses `Playwright` to render JavaScript-heavy sites.
-   **Stealth**: Implements `playwright-stealth` to avoid bot detection.
-   **Browser Types**: Supports `DESKTOP` (1920x1080) and `MOBILE` (iPhone 12 emulation). Mobile is preferred for cleaner, less cluttered layouts.
-   **Resilience**: Includes timeout handling and error recovery to ensure a single failed site doesn't crash the harvest.

### Cleaner (`src.media_lens.collection.cleaner`)
The `WebpageCleaner` transforms raw HTML into analysis-ready text.
-   **Core Dependency**: `Trafilatura` (primary extraction), `BeautifulSoup4` (fallback/cleanup).
-   **Normalization**: Removes ads, navigation, footers, and scripts.
-   **Output**: "Clean" HTML that retains semantic structure (headings, paragraphs) but strips visual clutter.

### Cleaning (`src.media_lens.collection.cleaning`)
Contains site-specific cleaning logic (`cleaner_for_site`).
-   **Strategy Pattern**: Allows for custom cleaning rules per domain (e.g., specific CSS selectors to remove for CNN vs. Fox News).

## Data Flow
1.  **Input**: List of URLs (from `SITES` config).
2.  **Scrape**: `Playwright` launches -> renders page -> saves `site.html`.
3.  **Clean**: `Trafilatura` parses `site.html` -> extracts main text -> saves `site-clean.html`.
