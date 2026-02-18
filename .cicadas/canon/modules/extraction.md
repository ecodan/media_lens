# Extraction Module

## Purpose
The Extraction module is the "brain" of Media Lens. It transforms unstructured HTML text into structured data and AI-generated insights.

## Key Components

### Extractor (`src.media_lens.extraction.extractor`)
The `ContextExtractor` identifies discrete news items within the cleaned HTML.
-   **Headline Extraction**: Uses an LLM to identify the main headlines and their associated URLs.
-   **Article Collection**: Fetches full article content for identified headlines.
-   **Validation**: Ensures a minimum number of articles (default: 5) are extracted per site.
-   **Output**: `site-extracted.json` (headlines + metadata) and individial article JSON files.

### Interpreter (`src.media_lens.extraction.interpreter`)
The `LLMWebsiteInterpreter` performs the high-level analysis on the structured content.
-   **Sentiment & Framing**: Sends article text to the LLM (Vertex/Claude) to answer specific questions:
    1.  What is the most important news?
    2.  What are the biggest issues?
    3.  How is the President portrayed? (Poor/Ok/Good/Excellent)
    4.  Adjectives for the US situation.
    5.  Adjectives for the President.
-   **Hybrid Approach**:
    -   **Rolling 7-Day**: Used for current week analysis to ensure freshness.
    -   **ISO Week**: Used for historical analysis to ensure consistency.
-   **Batch Processing**: Can interpret single days or aggregate over weeks.

### Agent (`src.media_lens.extraction.agent`)
The `Agent` class is an abstraction layer over the LLM providers.
-   **Providers**: Supports `Vertex AI` (Gemini) and `Anthropic` (Claude).
-   **Configuration**: Selects provider based on `AI_PROVIDER` env var.
-   **Retry Logic**: Handles API rate limits and transient failures.

### Job Directory Management (`src.media_lens.job_dir`)
The `JobDir` class encapsulates the logic for locating and managing timestamped job directories.
-   **Structure**: `jobs/YYYY/MM/DD/HHMMSS`.
-   **Discovery**: Finds latest job, lists all jobs, groups by week.

## Data Flow
1.  **Input**: `site-clean.html` (from Collection).
2.  **Extract**: `LLM` identifies headlines -> `site-extracted.json`.
3.  **Collect**: `Harvester` fetches full text for each headline -> `site-article-N.json`.
4.  **Interpret**: `LLM` analyzes all articles for a site/day -> `site-interpreted.json`.
5.  **Summarize**: Aggregates daily findings into `daily_news.txt`.
