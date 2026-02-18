# Technical Overview

## System Architecture

Media Lens operates as a linear pipeline that transforms raw web content into structured analysis and finally into static HTML reports.

```mermaid
graph TD
    A[Scheduler/CLI] --> B[Harvester]
    B --> C[Cleaner]
    C --> D[Extractor]
    D --> E[Interpreter (LLM)]
    E --> F[Summarizer]
    F --> G[Formatter]
    G --> H[Deployer]
    H --> I[Static Hosting]
```

## Core Components

### 1. Collection Layer
-   **Harvester (`src.media_lens.collection.harvester`)**: Orchestrates the fetching of content.
-   **Scraper (`src.media_lens.collection.scraper`)**: Uses `Playwright` to render JavaScript-heavy news sites and capture the DOM.
-   **Cleaner (`src.media_lens.collection.cleaner`)**: Uses `Trafilatura` and `BeautifulSoup` to normalize HTML, remove boilerplate, and extract the main content.

### 2. Extraction & Analysis Layer (The "Brain")
-   **Extractor (`src.media_lens.extraction.extractor`)**: Parses the cleaned HTML to identify headlines and article bodies.
-   **Interpreter (`src.media_lens.extraction.interpreter`)**: The interface to the LLM (vertex/claude). It sends content to the AI provider and receives structured JSON analysis (sentiment, framing, topics).
-   **Summarizer (`src.media_lens.extraction.summarizer`)**: Aggregates individual article analyses into daily and weekly summaries.

### 3. Presentation Layer
-   **Formatter (`src.media_lens.presentation.html_formatter`)**: Uses `Jinja2` templates to generate static HTML files from the analyzed JSON data, including complex weekly reports and individual standalone article pages.
-   **Deployer (`src.media_lens.presentation.deployer`)**: Handles the recursive upload of all generated assets to remote storage (SFTP or GCS), preserving directory hierarchies for reader-view articles.

### 4. Storage & Infrastructure
-   **Storage Adapter (`src.media_lens.storage_adapter`)**: Abstract interface for file operations, supporting both local filesystem and Google Cloud Storage.
-   **Job Directory Structure**: Data is organized hierarchically by time: `jobs/YYYY/MM/DD/HHMMSS/`.
-   **Containerization**: Docker support for both local development and cloud deployment (`Dockerfile`, `docker-compose.yml`).

## Technology Stack
-   **Language**: Python 3.9+
-   **Web Automation**: Playwright (for reliable rendering)
-   **Parsing**: BeautifulSoup4, Trafilatura
-   **AI/LLM**: Google Vertex AI (Gemini), Anthropic Claude
-   **Templating**: Jinja2
-   **CLI**: `argparse` based runner
-   **Package Management**: `uv`

## Data Flow
1.  **Harvest**: `URL` -> `Raw HTML` (saved to storage)
2.  **Clean**: `Raw HTML` -> `Cleaned Text/JSON`
3.  **Extract**: `Cleaned Text` -> `Structured Content (Headlines)`
4.  **Interpret**: `Structured Content` + `LLM Prompt` -> `Analysis JSON`
5.  **Summarize**: `Analysis JSONs` -> `Daily/Weekly Summary JSON`
6.  **Format**: `JSON Data` + `Templates` -> `HTML Weekly Report` + `Individual Article Pages`
7.  **Deploy**: `HTML Assets` -> `Web Server` (recursive upload)

## Infrastructure
-   **Local**: Runs via `uv run` or Docker Compose.
-   **Cloud**: Deployable to Google Cloud Run or similar container platforms.
-   **Secrets**: Managed via `.env` files (local) or Google Secret Manager (cloud).
