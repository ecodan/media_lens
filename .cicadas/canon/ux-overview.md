# UX Overview

## The Operator Experience (CLI)

The Media Lens system is primarily operated via a powerful Command Line Interface (CLI). This tool is designed for technical users who need granular control over the aggregation pipeline.

### Core Workflows

1.  **Harvest**: `python -m src.media_lens.runner run -s harvest`
    -   Scrapes content, cleans it, and saves it locally.
2.  **Analyze**: `python -m src.media_lens.runner run -s extract interpret`
    -   Uses LLMs to extract meaning and sentiment.
3.  **Report**: `python -m src.media_lens.runner run -s format deploy`
    -   Generates HTML reports and pushes them to the web server.
4.  **Full Pipeline**: `python -m src.media_lens.runner run -s harvest extract interpret format deploy`
    -   End-to-end execution.

### Key Concepts for Operators
-   **Job Directory**: All artifacts for a run reside in a date-stamped folder (`jobs/YYYY/MM/DD/HHMMSS`). This allows for easy debugging and re-processing.
-   **Incremental Processing**: The system tracks progress (cursors). Re-running a command only processes new data unless `--force` is used.
-   **Configuration**: Environment variables (`.env`) control API keys, storage paths, and feature flags.

## The Reader Experience (Web Report)

The end-user consumes the output as a static HTML website. The design emphasizes clarity and direct comparison.

### Landing Page (Current Events)
-   **Focus**: Immediate relevance.
-   **Content**: Displays analysis for the **last 7 days** on a rolling window.
-   **Layout**: Columns represent different news sources, rows represent days/topics.
-   **Interaction**: Users can hover over headlines for summaries or click the **"📖 Read"** link to access a local, distraction-free version of the full article.

### Weekly Archive (Historical)
-   **Focus**: Long-term trends and historical record.
-   **Content**: Locked analysis based on standard ISO weeks (Monday-Sunday).
-   **Stability**: Once a week is closed, its analysis does not change, providing a stable citation point.

## Visualization Strategy
-   **Side-by-Side**: The core visual mechanic is placing headlines from different sources next to each other to highlight framing differences.
-   **Sentiment Heatmaps**: Color-coding (e.g., Red=Negative, Green=Positive) provides an at-a-glance view of emotional tone.
-   **Topic Clustering**: Grouping related stories across sources to show what everyone is talking about vs. what only one outlet is covering.
