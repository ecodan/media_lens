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

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```


## Configuration

Create a `.env` in the project root with the following keys:
```bash
ANTHROPIC_API_KEY=

# set these if using the "deploy" step
FTP_HOSTNAME=
FTP_USERNAME=
FTP_KEY_PATH=
FTP_PORT=
FTP_PASSPHRASE=
FTP_REMOTE_PATH=

# set to true to use Google Cloud Storage
USE_CLOUD_STORAGE=false
LOCAL_STORAGE_PATH=$(pwd)/working/out

# set these if USE_CLOUD_STORAGE is true
GOOGLE_API_KEY=
GOOGLE_APPLICATION_CREDENTIALS=

```


## Usage

```bash
# Run main program
python src/media_lens/runner.py

# Run with scheduler (automated daily runs)
./run_media_lens_scheduled.sh

# Run full pipeline from harvest to deploy
./run_harvest_to_deploy.sh

# run individual steps
python src/media_lens/runner.py run -s <step1> <step2> ... -o /path/to/output

# override default sites
python src/media_lens/runner.py run -s <step1> <step2> -o /path/to/output --sites <site1> <site2>

# Run single module
python -m src.media_lens.<module_path>

# Start and Stop
1. CLI:
  # Start a run
  python src/media_lens/runner.py run -s harvest extract deploy -o /path/to/output

  # Stop a run (from another terminal)
  python src/media_lens/runner.py stop

2. HTTP API:
  # Start a run
  curl -X POST http://localhost:8080/run -H "Content-Type: application/json" -d '{"steps": ["harvest", "extract", "deploy"]}'

  # Check status
  curl http://localhost:8080/status

  # Stop a run
  curl -X POST http://localhost:8080/stop/your-run-id


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
