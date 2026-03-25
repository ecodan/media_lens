# UX Overview

> Canon document. Updated by the Synthesis agent at the close of each initiative.

## The Operator Experience (CLI & HTTP API)

Media Lens is operated by a single technical user via two interfaces: the CLI for direct control and the Flask HTTP API for scheduled cloud execution.

### CLI Workflows

The runner accepts a `-s STEPS` flag where steps are composed into a pipeline. All steps are individually addressable:

```bash
# Full daily workflow
python -m src.media_lens.runner run -s harvest extract interpret_weekly summarize_daily format deploy

# Scrape only (e.g., for later reprocessing)
python -m src.media_lens.runner run -s harvest_scrape --sites www.bbc.com

# Process existing content
python -m src.media_lens.runner run -s harvest_clean extract interpret -j jobs/2025/06/07/120000

# Incremental format + deploy (respects cursors)
python -m src.media_lens.runner run -s format deploy

# Force full regeneration (ignores cursors)
python -m src.media_lens.runner run -s format deploy --force-full-format --force-full-deploy

# Local dev mode (minimal Playwright restrictions)
python -m src.media_lens.runner run -s harvest extract --playwright-mode local
```

### Operator Mental Model

The operator thinks in three layers:
1. **Job directories** — each run produces `jobs/YYYY/MM/DD/HHmmss/`. Artifacts are traceable and reprocessable.
2. **Pipeline steps** — each step is independent and re-runnable. Failure at `extract` doesn't require re-scraping.
3. **Cursors** — `format_cursor.txt` and `deploy_cursor.txt` allow incremental runs. Reset with `reset-cursor` or `--rewind-days N`.

### Key Operator Operations

| Operation | Command | Notes |
|-----------|---------|-------|
| Full daily run | `run -s harvest extract interpret_weekly summarize_daily format deploy` | Standard production flow |
| Reprocess a week | `run -s format deploy --rewind-days 7` | Rewinds cursor then processes |
| Re-interpret history | `reinterpret-weeks -d 2025-01-01` | ISO week boundaries for historical |
| Check directory health | `audit --start-date 2025-01-01` | Validates article counts per site |
| Stop in-progress run | `stop` | Sets `RunState.stop_requested = True` |
| Reset cursors | `reset-cursor --all` | Forces full regeneration next run |

### HTTP API (Cloud Scheduling)

The Flask server on port 8080 exposes the same pipeline for cron-triggered execution:

```bash
# Standard daily run
curl -X POST http://localhost:8080/run \
  -d '{"steps": ["harvest", "extract", "interpret_weekly", "summarize_daily", "format", "deploy"]}'

# Check status
curl http://localhost:8080/status?run_id=your-run-id

# Stop a run
curl -X POST http://localhost:8080/stop/your-run-id
```

---

## The Reader Experience (Web Report)

The output is a self-contained static HTML website. No server-side logic; all pages are pre-rendered.

### Landing Page (`medialens.html`)

- **Content**: Rolling 7-day analysis window. Always reflects the most recent 7 days of coverage.
- **Layout**: Columns = news sources (CNN, BBC, Fox News). Rows = days.
- **Per-source per-day content**: Five AI-generated answers displayed per outlet:
  1. Most important news
  2. Biggest world issues
  3. U.S. President performance rating (Poor / Ok / Good / Excellent)
  4. Three adjectives: U.S. situation
  5. Three adjectives: President's performance/character
- **Interaction**: Click "📖 Read" on a headline to open the local reader view.

### Weekly Archive Pages (`medialens-YYYY-WNN.html`)

- **Content**: ISO week (Monday–Sunday) analysis. Stable once the week closes — historical records do not change.
- **Purpose**: Allows longitudinal comparison. A reader can compare any two weeks using consistent boundaries.
- **Discovery**: Accessible from the landing page via a week selector or direct URL.

### Article Reader Pages (`articles/{site}/{year}/{month}/{day}/{time}/*.html`)

- **Content**: Cleaned article text in a distraction-free format. Stripped of ads, navigation, and visual clutter.
- **Access**: Via the "📖 Read" link on each headline in the main report.
- **Storage**: Pre-generated as static HTML during the `format` step, served from the same static host.

---

## Report Design Principles

- **Side-by-side as the core mechanic**: Columns make framing differences immediately visible without requiring the reader to navigate between pages.
- **AI synthesis, not raw headlines**: Raw headlines from different outlets are hard to compare; the LLM normalizes them into comparable structured answers.
- **Historical stability**: Once a week is published and the ISO boundary passes, that week's interpretation does not change. This makes comparisons over time trustworthy.
- **Static-first**: The entire site can be served from any static host (S3, SFTP, GCS). No server dependency at read time.
