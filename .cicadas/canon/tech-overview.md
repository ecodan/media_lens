# Tech Overview

> Canon document. Updated by the Synthesis agent at the close of each initiative.

## What This Is

A Python async pipeline that scrapes news websites with Playwright, extracts article text, sends content to LLM providers (Anthropic Claude or Google Vertex AI/Gemini), and generates static HTML reports deployed via SFTP to a web server. All storage is file-based with optional Google Cloud Storage backend.

---

## Tech Stack

| Category | Selection | Notes |
|----------|-----------|-------|
| **Language/Runtime** | Python 3.10+ | Type annotations required everywhere |
| **Web scraping** | Playwright 1.40.0 + playwright-stealth | Stealth mode required for bot detection bypass |
| **HTML parsing** | BeautifulSoup4 4.13.3, trafilatura 2.0.0 | trafilatura is primary article extractor |
| **LLM interface** | litellm ≥1.0.0, anthropic 0.46.0, google-cloud-aiplatform 1.71.1 | litellm routes to both providers |
| **Web framework** | Flask 2.3.3, gunicorn 23.0.0 | HTTP control plane for cloud VM |
| **Templating** | Jinja2 3.1.6 | HTML report generation |
| **Cloud storage** | google-cloud-storage 2.13.0 | Optional, switched via `USE_CLOUD_STORAGE` |
| **SFTP deployment** | paramiko 3.5.1 | Uploads staging/ to remote web server |
| **CLI** | click 8.1.8 | Runner entry point |
| **Retry logic** | tenacity | LLM API retries (5 attempts, exponential backoff 4–60s) |
| **Testing** | pytest 8.3.4+, pytest-asyncio, pytest-cov | `test/` directory |
| **Build/packaging** | uv, hatchling | Use `uv run` for execution |
| **Linting** | ruff | Configured in pyproject.toml |
| **Deployment** | Docker + Google Cloud VM | Not Cloud Run — Playwright requires persistent container |

---

## Project Structure

```
media_lens/
├── src/media_lens/              # Main source code
│   ├── collection/              # Web scraping & HTML cleaning
│   │   ├── harvester.py         # Orchestrates scrape → clean
│   │   ├── scraper.py           # Playwright page fetcher
│   │   ├── cleaner.py           # HTML cleaning pipeline
│   │   └── cleaning.py          # Site-specific cleaner implementations
│   ├── extraction/              # Content analysis layer
│   │   ├── agent.py             # LLM provider abstraction (LiteLLMAgent)
│   │   ├── headliner.py         # LLM headline extraction
│   │   ├── collector.py         # Full article text fetching
│   │   ├── extractor.py         # Orchestrates headliner + collector
│   │   ├── interpreter.py       # 5-question LLM analysis
│   │   ├── summarizer.py        # Daily news summary generation
│   │   └── exceptions.py        # Domain exception types
│   ├── presentation/            # Output generation & deployment
│   │   ├── html_formatter.py    # Jinja2 HTML generation with cursor
│   │   └── deployer.py          # SFTP upload with cursor
│   ├── common.py                # Logger, constants, RunState, utilities
│   ├── runner.py                # CLI entry point & pipeline orchestration
│   ├── storage_adapter.py       # Local/GCS storage abstraction (singleton)
│   ├── storage.py               # Global shared_storage instance
│   ├── job_dir.py               # JobDir: hierarchical path management
│   ├── directory_manager.py     # DirectoryManager: path generation
│   ├── cloud_entrypoint.py      # Flask HTTP API server
│   ├── auditor.py               # Job directory completeness validation
│   ├── scheduler.py             # Daily scheduling utility
│   └── secret_manager.py        # Google Cloud Secret Manager integration
├── config/templates/            # Jinja2 HTML templates (.j2 files)
│   ├── index_template.j2        # Landing page (medialens.html)
│   ├── weekly_template.j2       # Weekly reports
│   └── article_template.j2      # Reader-view article pages
├── test/                        # pytest test suite
├── pyproject.toml               # Dependencies, build config
├── requirements.txt             # Pinned deps
├── Dockerfile                   # Cloud VM container (x86_64)
├── Dockerfile.local             # Local dev container (ARM64)
├── docker-compose.yml           # Base compose config
├── docker-compose.local.yml     # Local overrides
└── startup-script.sh            # GCP VM startup script
```

---

## Architecture

### System Design

Media Lens is a **linear batch pipeline** where each step reads from storage and writes structured output consumed by the next step. All steps are individually addressable via the CLI's `-s` flag. The runner orchestrates steps sequentially within a single async execution context.

Two orthogonal concerns are layered over the pipeline: (1) a **storage abstraction** that makes all I/O backend-agnostic (local vs. GCS), and (2) a **cursor mechanism** that makes the format and deploy steps incrementally skip already-processed content.

The system has two entry points: the CLI (`runner.py`) for operator use and a **Flask HTTP API** (`cloud_entrypoint.py`) for scheduled cloud execution.

### Key Components

| Component | Responsibility | Key Files |
|-----------|----------------|-----------|
| Runner | CLI parsing, step sequencing, step validation | `runner.py` |
| Harvester | Scrape → clean orchestration | `collection/harvester.py` |
| WebpageScraper | Playwright-based page fetching | `collection/scraper.py` |
| WebpageCleaner | Site-specific HTML stripping | `collection/cleaner.py`, `cleaning.py` |
| ContextExtractor | Headline extraction + article collection | `extraction/extractor.py` |
| LLMHeadlineExtractor | LLM headline identification | `extraction/headliner.py` |
| ArticleCollector | Full-text article fetching | `extraction/collector.py` |
| LLMWebsiteInterpreter | 5-question LLM analysis | `extraction/interpreter.py` |
| DailySummarizer | Daily prose summary | `extraction/summarizer.py` |
| Agent / LiteLLMAgent | LLM provider abstraction | `extraction/agent.py` |
| HtmlFormatter | Jinja2 HTML generation + format cursor | `presentation/html_formatter.py` |
| Deployer | SFTP upload + deploy cursor | `presentation/deployer.py` |
| StorageAdapter | File I/O abstraction (local/GCS singleton) | `storage_adapter.py` |
| JobDir | Hierarchical job path parsing/listing | `job_dir.py` |
| Cloud Entrypoint | Flask HTTP control API | `cloud_entrypoint.py` |

### Data Flow

```
URLs (SITES_DEFAULT)
  → [WebpageScraper]      → jobs/YYYY/MM/DD/HHmmss/{site}.html
  → [WebpageCleaner]      → jobs/YYYY/MM/DD/HHmmss/{site}-clean.html
  → [LLMHeadlineExtractor]→ jobs/YYYY/MM/DD/HHmmss/{site}-clean-extracted.json
  → [ArticleCollector]    → jobs/YYYY/MM/DD/HHmmss/{site}-article-N.json
  → [LLMWebsiteInterpreter]→ intermediate/{job_ts}/{site}-interpreted.json
  → [DailySummarizer]     → jobs/YYYY/MM/DD/HHmmss/daily_news.txt
  → [HtmlFormatter]       → staging/medialens.html, staging/medialens-YYYY-WNN.html, staging/articles/...
  → [Deployer]            → Remote SFTP server
```

### Key Architecture Decisions

- **Singleton StorageAdapter**: One global instance (`storage.shared_storage`) accessed by all modules. Prevents multiple GCS client initializations and allows backend switching at startup.
- **Cloud VM, not Cloud Run**: Playwright requires a persistent container environment; Cloud Run's ephemeral instances are incompatible.
- **LiteLLM routing**: Single `litellm.completion()` call routes to Anthropic or Vertex AI based on model string prefix. Avoids provider-specific SDK coupling everywhere.
- **Cursor-based incremental processing**: Format and deploy steps use timestamp cursors to skip re-processing. Essential for cost control in production.
- **Hybrid temporal analysis**: Current week uses rolling 7-day (always fresh for users); historical weeks use ISO Mon–Sun boundaries (stable for citation and comparison).
- **HTML truncation at 100KB**: Prevents Vertex AI quota exhaustion. Applied in `WebpageCleaner.clean_html()`.
- **WebpageScraper in ArticleCollector**: Required to bypass Cloudflare 403 blocks (e.g., CNN). trafilatura alone is insufficient for some outlets.

---

## Data Models

### Job Directory Layout
```
jobs/
└── YYYY/
    └── MM/
        └── DD/
            └── HHmmss/
                ├── {site}.html                    # Raw scraped HTML
                ├── {site}-clean.html              # Cleaned HTML (≤100KB)
                ├── {site}-clean-extracted.json    # Headlines + metadata
                ├── {site}-article-N.json          # Article N full text (0-indexed)
                └── daily_news.txt                 # Daily prose summary
intermediate/
└── {job_timestamp}/
    └── {site}-interpreted.json                    # LLM 5-question analysis
weekly-{YYYY-WNN}-interpreted.json                 # Weekly interpretation
staging/
├── medialens.html                                 # Main landing page
├── medialens-{YYYY-WNN}.html                      # Weekly archive pages
└── articles/{site}/{year}/{month}/{day}/{time}/   # Article reader pages
```

### Extracted Headlines File (`{site}-clean-extracted.json`)
```json
{
  "stories": [
    {
      "headline": "Headline text",
      "url": "/news/article-path",
      "summary": "Brief summary",
      "article_text": "jobs/2025/03/24/140530/www.cnn.com-article-0.json"
    }
  ],
  "metadata": {
    "model": {
      "name": "claude-sonnet-4-5",
      "provider": "anthropic",
      "temperature": 0.7,
      "max_tokens": 4096
    },
    "generated_at": "2025-03-24T14:05:30+00:00"
  }
}
```

### Article Text File (`{site}-article-N.json`)
```json
{
  "title": "Full article headline",
  "text": "Full article body text...",
  "url": "https://www.cnn.com/news/article"
}
```

### Interpretation File (`intermediate/{job_ts}/{site}-interpreted.json`)
```json
[
  {"question": "What is the most important news right now?", "answer": "..."},
  {"question": "What are the biggest issues in the world right now?", "answer": "..."},
  {"question": "For articles referring to the president of the U.S. (Donald Trump), is the president doing a [poor, ok, good, excellent] job based on the portrayal?", "answer": "Good - ..."},
  {"question": "What are three adjectives that best describe the situation in the U.S.?", "answer": "Polarized, Dynamic, Uncertain"},
  {"question": "What are three adjectives that best describe the job performance and character of the U.S. President?", "answer": "Assertive, Controversial, Focused"}
]
```

### Weekly Interpretation File (`intermediate/weekly-{YYYY-WNN}-interpreted.json`)
```json
{
  "week": "2025-W12",
  "calendar_days_span": 7,
  "days_count": 6,
  "interpretations": [
    {
      "site": "www.cnn.com",
      "analysis": [{"question": "...", "answer": "..."}, ...]
    }
  ]
}
```

---

## API & Interface Surface

### CLI Entry Point (`runner.py`)

```
run -s STEPS [--job-dir DIR] [--start-date DATE] [--end-date DATE]
    [--sites SITE...] [--playwright-mode local|cloud]
    [--force-full-format] [--force-full-deploy] [--rewind-days N]
    [--run-id ID]
summarize [-f|--force]
reinterpret-weeks -d DATE [--no-overwrite]
stop
reset-cursor [--format] [--deploy] [--all]
audit [--start-date DATE] [--end-date DATE] [--no-report]
```

Valid steps: `harvest`, `harvest_scrape`, `harvest_clean`, `re-harvest`, `extract`, `interpret`, `interpret_weekly`, `summarize_daily`, `format`, `deploy`

### Flask HTTP API (`cloud_entrypoint.py`, port 8080)

```
GET  /              # App info
GET  /health        # Health check
POST /run           # Execute pipeline steps
POST /weekly        # Process weekly content
POST /summarize     # Generate daily summaries
POST /stop/{run_id} # Stop running pipeline
GET  /status        # Check run status
```

### External Dependencies

| Service / API | Purpose | Auth method |
|---------------|---------|-------------|
| Anthropic API | Claude LLM inference | `ANTHROPIC_API_KEY` env var |
| Google Vertex AI | Gemini LLM inference | Service account JSON or workload identity |
| Google Cloud Storage | Optional file storage backend | `GOOGLE_APPLICATION_CREDENTIALS` |
| Google Cloud Secret Manager | Production secrets management | Workload identity on GCP VM |
| SFTP server | HTML report deployment | `FTP_HOST/USER/PASSWORD` env vars |

---

## Implementation Conventions

### Naming

| Construct | Convention | Example |
|-----------|-----------|---------|
| Classes | PascalCase | `WebpageCleaner`, `LiteLLMAgent` |
| Functions/methods | snake_case | `clean_html()`, `extract_headlines()` |
| Constants | UPPER_SNAKE_CASE | `SITES_DEFAULT`, `LOG_FORMAT` |
| Files | snake_case | `html_formatter.py`, `storage_adapter.py` |
| Test classes | `Test` prefix | `TestWebpageCleaner` |
| Test methods | `test_` prefix | `test_clean_removes_scripts()` |

### Key Patterns

- **Imports**: All at top of file (never inside methods unless absolutely required)
- **Type hints**: Required on all function parameters, return types, and variable declarations
- **Logging**: Use `create_logger(LOGGER_NAME)` from `common.py`. Format: `%(asctime)s [%(levelname)s] <%(filename)s:%(lineno)s> %(message)s`
- **Error handling**: Use specific exception types from `extraction/exceptions.py`. Log before raising/swallowing.
- **Async**: Use `async/await` for all I/O-bound operations. `asyncio.run()` at the CLI entry point.
- **Paths**: Use `pathlib.Path` objects. Never string concatenation for paths.
- **Credentials**: Load from `.env` file (local) or Secret Manager (cloud). Never hardcoded.
- **Testing**: Mock at the storage/LLM boundary. pytest-asyncio for async tests.
- **Retry**: Use `tenacity` for LLM API calls (configured in `Agent.invoke()`).

---

## Module Snapshots

- [`modules/collection.md`](modules/collection.md) — Web scraping & HTML cleaning
- [`modules/extraction.md`](modules/extraction.md) — Content analysis & LLM interpretation
- [`modules/presentation.md`](modules/presentation.md) — HTML generation & SFTP deployment
- [`modules/storage.md`](modules/storage.md) — Storage abstraction layer
- [`modules/runner.md`](modules/runner.md) — CLI orchestration & pipeline control

---

## Open Questions

- Should `interpret` and `interpret_weekly` be merged into a single step? They overlap in purpose and both write to `intermediate/`. — Operator / low urgency
- `LiteLLMAgent` model string format differs between providers; should there be a model config file? — Low urgency
