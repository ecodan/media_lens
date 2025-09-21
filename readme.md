# Media Lens

A Python-based tool for comparative analysis of media worldviews through automated headline and content analysis.

## Overview

Media Lens systematically analyzes how different news sources present world events by comparing their headline choices and content framing. The system scrapes front pages of news websites, extracts top headlines, and uses Large Language Models (LLMs) to perform sentiment and framing analysis on the associated stories.

A live version of this tool is available at [Media Lens](https://www.dancripe.com/reports/medialens.html).

## Key Features

- **Hybrid Analysis Approach**: Rolling 7-day analysis for current events, ISO week boundaries for historical tracking
- Automated scraping of news site front pages
- Extraction and analysis of top N(=5) headlines per source
- LLM-powered content analysis and sentiment detection
- Side-by-side comparison view of different media sources
- Daily updated analysis with fresh 7-day rolling windows
- Modular architecture with single-responsibility components
- HTML report generation with comparative analysis

## Analysis Approach

Media Lens uses a **hybrid temporal analysis system** designed to provide both current relevance and historical consistency:

### Rolling 7-Day Analysis (Current Events)
- **Landing Page Display**: Always shows analysis of the most recent 7 days
- **Daily Updates**: Every day, the analysis window shifts to include the latest day and drop the oldest
- **Cross-Week Boundaries**: Looks back exactly 7 days regardless of calendar week boundaries
- **Fresh Insights**: Provides the most current view of media trends and coverage

### ISO Week Analysis (Historical Tracking)
- **Historical Weeks**: Completed weeks use traditional Monday-Sunday ISO boundaries
- **Consistent Comparison**: Enables reliable week-to-week historical comparisons
- **Archive Stability**: Historical analyses remain constant and don't shift over time

### Key Questions Analyzed
The system answers five core questions about media coverage:
1. What is the most important news right now?
2. What are the biggest issues in the world right now?
3. How is the U.S. President performing based on media portrayal?
4. What three adjectives best describe the situation in the U.S.?
5. What three adjectives best describe the U.S. President's performance and character?

## Architecture

The project follows a modular design with dedicated components for each stage of the pipeline:

### Core Packages
- **Collection**: Content scraping and cleaning.
- **Extraction**: Headline and article content isolation, summarization and interpretation.
- **Presentation**: Outputing as HTML and SFTP to hosting site.

### Supporting Components
- **Aggregators**: High-level pipeline orchestration
- **Storage**: File system-based data persistence (database-ready)

## Data Flow

1. Scrapers collect raw HTML from configured news sources
2. Cleaners normalize and sanitize the raw content
3. Extractors identify and isolate headlines and articles
4. Summarizers process full articles into analyzable chunks
5. Analyzers perform LLM-based content analysis
6. Aggregators combine results from multiple sources
7. Reporters generate comparative HTML views

## Storage

Currently implements a file system-based storage solution for simplicity and rapid development. The architecture is designed to easily accommodate future database integration through storage interface abstraction.

## Future Enhancements

- Database integration for improved data management
- Real-time analysis and report generation
- Additional news source support
- Extended analysis metrics
- API endpoint for programmatic access
- Interactive web interface

## Requirements

- Python 3.8+ (tested with Python 3.12)
- See requirements.txt for dependencies
- AI Provider API access:
  - **Anthropic Claude** (default) - requires API key
  - **Google Vertex AI** (optional) - requires GCP service account and project setup
- SFTP information if you want to push the file to a web server

## Development Setup
See readme-deployment.md for deployment instructions.


## Usage

### CLI Commands

#### Run Pipeline
Execute workflow steps individually or in combination:

```bash
# Run main program (basic)
python -m src.media_lens.runner

# Run specific steps
python -m src.media_lens.runner run -s harvest extract interpret_weekly summarize_daily format deploy

# Available steps:
# - harvest: Complete scraping and cleaning workflow
# - harvest_scrape: Scraping only (saves raw HTML files)
# - harvest_clean: Cleaning only (processes existing HTML files)
# - re-harvest: Re-harvest existing content
# - extract: Extract structured data from cleaned content
# - interpret: Generate AI interpretations for individual runs
# - interpret_weekly: Generate weekly AI interpretations (uses hybrid approach)
# - summarize_daily: Create daily summaries
# - format: Generate HTML output files
# - deploy: Deploy files to remote server

# Override default sites
python -m src.media_lens.runner run -s harvest --sites www.bbc.com www.cnn.com

# Process specific job directory
python -m src.media_lens.runner run -s extract interpret -j jobs/2025/06/07/120000

# Process date range
python -m src.media_lens.runner run -s format --start-date 2025-01-01 --end-date 2025-01-31

# Force full processing (ignore cursors)
python -m src.media_lens.runner run -s format --force-full-format
python -m src.media_lens.runner run -s deploy --force-full-deploy

# Rewind cursors before running
python -m src.media_lens.runner run -s format deploy --rewind-days 7

# Set browser mode for local development
python -m src.media_lens.runner run -s harvest --playwright-mode local

# Assign custom run ID for tracking
python -m src.media_lens.runner run -s harvest --run-id my-custom-run
```

#### Daily Summarization
```bash
# Summarize all days
python -m src.media_lens.runner summarize

# Force re-summarization
python -m src.media_lens.runner summarize --force
```

#### Weekly Reinterpretation
```bash
# Reinterpret weekly content from specific date (uses hybrid approach)
python -m src.media_lens.runner reinterpret-weeks --date 2025-01-01

# Don't overwrite existing interpretations
python -m src.media_lens.runner reinterpret-weeks --date 2025-01-01 --no-overwrite

# Note: Current week uses rolling 7-day analysis, historical weeks use ISO boundaries
```

#### Cursor Management
```bash
# Reset both cursors (forces full regeneration/deployment)
python -m src.media_lens.runner reset-cursor

# Reset specific cursors
python -m src.media_lens.runner reset-cursor --format
python -m src.media_lens.runner reset-cursor --deploy
python -m src.media_lens.runner reset-cursor --all
```

#### Audit Directories
```bash
# Audit all directories
python -m src.media_lens.runner audit

# Audit specific date range
python -m src.media_lens.runner audit --start-date 2025-01-01 --end-date 2025-01-31

# Skip generating audit report file
python -m src.media_lens.runner audit --no-report
```

#### Stop Running Process
```bash
# Stop current run
python -m src.media_lens.runner stop
```

### Web API Endpoints

The application includes a Flask web server that can be started locally or via Docker:

**Local Development:**
```bash
python -m src.media_lens.cloud_entrypoint
```

**Docker (preferred for local testing):**
```bash
docker compose --profile local up --build
```

#### Pipeline Execution
```bash
# Start pipeline run
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"steps": ["harvest", "extract", "interpret", "format", "deploy"]}'

# Start with custom sites
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"steps": ["harvest"], "sites": ["www.bbc.com", "www.cnn.com"]}'

# Start with cursor rewind
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"steps": ["format", "deploy"], "rewind_days": 7}'

# Start with custom run ID
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"steps": ["harvest"], "run_id": "my-custom-run"}'
```

#### Weekly Processing
```bash
# Process current week only (uses rolling 7-day analysis)
curl -X POST http://localhost:8080/weekly \
  -H "Content-Type: application/json" \
  -d '{"current_week_only": true}'

# Process specific historical weeks (uses ISO week boundaries)
curl -X POST http://localhost:8080/weekly \
  -H "Content-Type: application/json" \
  -d '{"specific_weeks": ["2025-W08", "2025-W09"], "overwrite": true}'

# Disable rolling analysis for current week (force ISO boundaries)
curl -X POST http://localhost:8080/weekly \
  -H "Content-Type: application/json" \
  -d '{"current_week_only": true, "use_rolling_for_current": false}'
```

#### Summarization
```bash
# Run daily summarization
curl -X POST http://localhost:8080/summarize \
  -H "Content-Type: application/json" \
  -d '{"force": false}'

# Force re-summarization
curl -X POST http://localhost:8080/summarize \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

#### Status and Control
```bash
# Check overall status
curl http://localhost:8080/status

# Check specific run status
curl http://localhost:8080/status?run_id=your-run-id

# Stop a running process
curl -X POST http://localhost:8080/stop/your-run-id

# Health check
curl http://localhost:8080/health

# Application info
curl http://localhost:8080/
```

### Environment Variables

```bash
# Browser configuration for local development
export PLAYWRIGHT_MODE=local  # or 'cloud' for container environments

# AI Provider Configuration
export AI_PROVIDER=claude  # Options: "claude", "vertex"

# Anthropic Claude Configuration
export ANTHROPIC_API_KEY=your-anthropic-api-key

# Google Vertex AI Configuration (required when AI_PROVIDER=vertex)
export GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json
export VERTEX_AI_PROJECT_ID=your-gcp-project-id
export VERTEX_AI_LOCATION=us-central1
export VERTEX_AI_MODEL=gemini-2.5-flash

# Google Cloud Storage Configuration
export GOOGLE_CLOUD_PROJECT=your-gcp-project-id
export GCP_STORAGE_BUCKET=your-storage-bucket-name
export USE_CLOUD_STORAGE=false

# FTP Deployment Settings
export FTP_REMOTE_PATH=/path/to/remote/directory

# Local Storage Configuration
export LOCAL_STORAGE_PATH=/path/to/your/working/directory
```

### Quick Start Examples

```bash
# Full daily workflow (interpret_weekly uses hybrid approach)
python -m src.media_lens.runner run -s harvest extract interpret_weekly summarize_daily format deploy

# Local development with minimal browser restrictions
python -m src.media_lens.runner run -s harvest extract --playwright-mode local

# Scrape only (for later processing)
python -m src.media_lens.runner run -s harvest_scrape --sites www.bbc.com

# Process existing scraped content
python -m src.media_lens.runner run -s harvest_clean extract interpret -j jobs/2025/06/07/120000

# Incremental deployment (only new files)
python -m src.media_lens.runner run -s format deploy

# Force complete regeneration
python -m src.media_lens.runner run -s format deploy --force-full-format --force-full-deploy

# Note: Current week analysis automatically uses rolling 7-day windows,
# while historical weeks maintain ISO week boundaries for consistency
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
```
MIT License

Copyright (c) 2025 Dan Cripe

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
