# Media Lens

A Python-based tool for comparative analysis of media worldviews through automated headline and content analysis.

## Overview

Media Lens systematically analyzes how different news sources present world events by comparing their headline choices and content framing. The system scrapes front pages of news websites, extracts top headlines, and uses Large Language Models (LLMs) to perform sentiment and framing analysis on the associated stories.

A live version of this tool is available at [Media Lens](https://www.dancripe.com/reports/medialens.html).

## Key Features

- Automated scraping of news site front pages
- Extraction and analysis of top N(=5) headlines per source
- LLM-powered content analysis and sentiment detection
- Side-by-side comparison view of different media sources
- Modular architecture with single-responsibility components
- HTML report generation with comparative analysis

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
- Anthropic Claude developer API
- SFTP information if you want to push the file to a web server

## Development Setup
See readme-deployment.md for deployment instructions.


## Usage

### CLI Commands

#### Run Pipeline
Execute workflow steps individually or in combination:

```bash
# Run main program (basic)
python src/media_lens/runner.py

# Run specific steps
python src/media_lens/runner.py run -s harvest extract interpret format deploy

# Available steps:
# - harvest: Complete scraping and cleaning workflow
# - harvest_scrape: Scraping only (saves raw HTML files)  
# - harvest_clean: Cleaning only (processes existing HTML files)
# - extract: Extract structured data from cleaned content
# - interpret: Generate AI interpretations for individual runs
# - interpret_weekly: Generate weekly AI interpretations
# - summarize_daily: Create daily summaries
# - format: Generate HTML output files
# - deploy: Deploy files to remote server

# Override default sites
python src/media_lens/runner.py run -s harvest --sites www.bbc.com www.cnn.com

# Process specific job directory
python src/media_lens/runner.py run -s extract interpret -j jobs/2025/06/07/120000

# Process date range
python src/media_lens/runner.py run -s format --start-date 2025-01-01 --end-date 2025-01-31

# Force full processing (ignore cursors)
python src/media_lens/runner.py run -s format --force-full-format
python src/media_lens/runner.py run -s deploy --force-full-deploy

# Rewind cursors before running
python src/media_lens/runner.py run -s format deploy --rewind-days 7

# Set browser mode for local development
python src/media_lens/runner.py run -s harvest --playwright-mode local
```

#### Daily Summarization
```bash
# Summarize all days
python src/media_lens/runner.py summarize

# Force re-summarization
python src/media_lens/runner.py summarize --force
```

#### Weekly Reinterpretation
```bash
# Reinterpret weekly content from specific date
python src/media_lens/runner.py reinterpret-weeks --date 2025-01-01

# Don't overwrite existing interpretations
python src/media_lens/runner.py reinterpret-weeks --date 2025-01-01 --no-overwrite
```

#### Cursor Management
```bash
# Reset both cursors (forces full regeneration/deployment)
python src/media_lens/runner.py reset-cursor

# Reset specific cursors
python src/media_lens/runner.py reset-cursor --format
python src/media_lens/runner.py reset-cursor --deploy
python src/media_lens/runner.py reset-cursor --all
```

#### Audit Directories
```bash
# Audit all directories
python src/media_lens/runner.py audit

# Audit specific date range
python src/media_lens/runner.py audit --start-date 2025-01-01 --end-date 2025-01-31

# Skip generating audit report file
python src/media_lens/runner.py audit --no-report
```

#### Stop Running Process
```bash
# Stop current run
python src/media_lens/runner.py stop
```

### Web API Endpoints

Start the web server:
```bash
python src/media_lens/cloud_entrypoint.py
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
# Process current week only
curl -X POST http://localhost:8080/weekly \
  -H "Content-Type: application/json" \
  -d '{"current_week_only": true}'

# Process specific weeks
curl -X POST http://localhost:8080/weekly \
  -H "Content-Type: application/json" \
  -d '{"specific_weeks": ["2025-W08", "2025-W09"], "overwrite": true}'
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

# API keys and deployment settings
export ANTHROPIC_API_KEY=your-api-key
export FTP_REMOTE_PATH=/path/to/remote/directory
```

### Quick Start Examples

```bash
# Full daily workflow
python src/media_lens/runner.py run -s harvest extract interpret_weekly summarize_daily format deploy

# Local development with minimal browser restrictions
python src/media_lens/runner.py run -s harvest extract --playwright-mode local

# Scrape only (for later processing)
python src/media_lens/runner.py run -s harvest_scrape --sites www.bbc.com

# Process existing scraped content
python src/media_lens/runner.py run -s harvest_clean extract interpret -j jobs/2025/06/07/120000

# Incremental deployment (only new files)
python src/media_lens/runner.py run -s format deploy

# Force complete regeneration
python src/media_lens/runner.py run -s format deploy --force-full-format --force-full-deploy
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
