# Product Overview

> Canon document. Updated by the Synthesis agent at the close of each initiative.

## What This Is

Media Lens is a Python-based automated pipeline that scrapes major news websites, extracts article content, and uses LLMs to produce comparative analysis of how different outlets frame the same news. It generates and deploys static HTML reports that let readers see side-by-side differences in coverage tone, framing, and topic selection. Live instance: https://www.dancripe.com/reports/medialens.html

## Why It Exists

Different news outlets cover the same events with profoundly different emphasis, tone, and framing. Manually monitoring multiple sources daily is impractical. Media Lens automates this cross-source surveillance, producing a structured, comparable record that is difficult to achieve by hand and valuable for anyone trying to understand how media shapes perception.

---

## Users & Journeys

### The Operator — Solo technical owner

**Who they are:** A developer who maintains and runs the pipeline, manages configuration, and ensures daily execution. They interact exclusively via the CLI and HTTP API.

**Their journey:** They configure environment variables, run `python -m src.media_lens.runner run -s harvest extract interpret_weekly summarize_daily format deploy` on a schedule (or let the Cloud VM cron job do it), monitor logs for failures, and occasionally re-process historical weeks using `reinterpret-weeks`. Success is a daily HTML report deployed to the web server by mid-morning without manual intervention.

**Key needs:**
- Granular step control (run only `harvest`, only `format deploy`, etc.)
- Incremental processing — avoid recomputing unchanged data
- Observability — clear logs and run status endpoints
- Recovery paths — `--force-full-format`, `reset-cursor`, `reinterpret-weeks`

---

### The Reader — Media-literate general public

**Who they are:** Someone who visits the static HTML report to get a quick sense of how different outlets are covering today's news. Not technical; consumes the output passively.

**Their journey:** They land on `medialens.html`, see a rolling 7-day overview with columns for each news source. They scan AI-generated answers to five questions (most important news, biggest issues, presidential performance adjectives) and compare framing across CNN, BBC, and Fox News. They click "📖 Read" to access a local distraction-free reader view of an article.

**Key needs:**
- Clear, side-by-side comparison layout
- Fast-loading static pages (no backend required)
- Historical weekly archives that don't change once closed

---

## Core Features (Current)

| Feature | Description | Status |
|---------|-------------|--------|
| Multi-source scraping | Playwright-based scraping with stealth mode for CNN, BBC, Fox News | Shipped |
| Site-specific HTML cleaning | CSS-selector-based cleaners per outlet (pattern strategy) | Shipped |
| LLM headline extraction | Chain-of-thought extraction of top 5 headlines + summaries per site | Shipped |
| Article collection | Full-text article fetching via WebpageScraper + trafilatura | Shipped |
| LLM media analysis | 5-question interpretation (importance, issues, president rating, adjectives) | Shipped |
| Hybrid temporal analysis | Rolling 7-day for current week; ISO week boundaries for history | Shipped |
| Daily news summary | Unbiased prose summary (≤500 words) from all sources | Shipped |
| Static HTML report generation | Jinja2-templated index + weekly + article reader pages | Shipped |
| Incremental format/deploy | Cursor-based processing to skip unchanged content | Shipped |
| SFTP deployment | Paramiko-based upload of staging/ to remote web server | Shipped |
| Cloud VM scheduling | GCP VM with Cloud Scheduler triggers HTTP `/run` endpoint | Shipped |
| Flask HTTP control API | REST endpoints for triggering and monitoring pipeline runs | Shipped |
| Local + GCS storage | Dual storage backends switchable via `USE_CLOUD_STORAGE` | Shipped |
| Audit tool | Directory completeness validation across date ranges | Shipped |

## Out of Scope (Intentional)

- **Real-time analysis** — The pipeline runs daily (batch), not continuously
- **User accounts / personalization** — Reports are public and static
- **Comment sentiment / social media** — Only structured news article content
- **Automatic source expansion** — Sites are configured manually, not crawled
- **Database persistence** — All storage is file-based JSON/HTML

---

## Success Criteria

- Daily report published to live URL before 10:00 AM UTC on each run day
- ≥5 articles extracted per site per run
- No failed weeks in the weekly interpretation files
- Format and deploy steps complete incrementally in <2 minutes for typical daily runs

---

## Open Questions

- Should a fourth outlet (e.g., Reuters, NYT) be added to the default `SITES_DEFAULT`? — Operator / low urgency
- Should the daily summary generation be gated on a minimum article count threshold? — Operator / medium urgency
