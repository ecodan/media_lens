# Model Upgrade Evaluation (model-upgrade-eval)

This directory contains the dataset preparation and evaluation setup for the `gemini-2.5-flash` → Gemini 3+ model upgrade initiative.

## Overview

The initiative evaluates four LLM model candidates across three tasks:
1. **Headline Extraction** — extract prominent headlines from news HTML
2. **Interpretation** — 5-question media analysis of article content
3. **Daily Summary** — prose summary of the day's news

All evaluation uses the [gavel-ai](../../../gavel-ai/) framework with test data from `working/gcs/` (your local golden dataset).

## Quick Start

### 1. Prepare Scenarios

```bash
cd eval
python prepare_dataset.py
```

This creates three scenario JSON files in `data/`:
- `headline-extraction-scenarios.json` (25 scenarios)
- `interpretation-scenarios.json` (25 scenarios, ~14 with golden references)
- `daily-summary-scenarios.json` (25 scenarios)

Each scenario has:
- `id`: unique identifier
- `input`: LLM input (HTML, article text, etc.)
- `expected_behavior`: what the model should do
- `golden_reference`: expected output (or `null` if not available)

### 2. Copy Scenarios to Gavel-AI

Link (or copy) the scenario files into the gavel-ai evaluation directories:

```bash
# From media_lens project root
cd ../gavel-ai/.gavel/evaluations

# For each eval, copy or symlink the appropriate scenario file
ln -s ../../../media_lens/eval/data/headline-extraction-scenarios.json media-lens-headline-extraction/data/scenarios.json
ln -s ../../../media_lens/eval/data/interpretation-scenarios.json media-lens-interpretation/data/scenarios.json
ln -s ../../../media_lens/eval/data/daily-summary-scenarios.json media-lens-daily-summary/data/scenarios.json
```

### 3. Run Evals in Gavel-AI

From the gavel-ai project:

```bash
# Run headline extraction eval for all models
gavel oneshot run --eval media-lens-headline-extraction

# Run interpretation eval
gavel oneshot run --eval media-lens-interpretation

# Run daily summary eval
gavel oneshot run --eval media-lens-daily-summary
```

Results are written to `.gavel/evaluations/{eval-name}/runs/{timestamp}/report.html`.

### 4. Review Results

Open each HTML report to see per-model, per-judge scores and verdicts.

## Directory Structure

```
eval/
├── README.md                          # This file
├── prepare_dataset.py                 # Dataset preparation script
├── data/                              # gitignored — generated scenarios
│   ├── headline-extraction-scenarios.json
│   ├── interpretation-scenarios.json
│   └── daily-summary-scenarios.json
```

## Configuration

Edit `prepare_dataset.py` to adjust:
- `GOLDEN_ROOT`: path to golden data (default: `working/gcs`)
- `HEADLINE_TARGET`, `INTERPRETATION_TARGET`, `SUMMARY_TARGET`: number of scenarios per task (default: 25 each)
- `SITES`: news sites to include (default: BBC, CNN, Fox News)

## Troubleshooting

**"No scenario files generated"**
- Verify `working/gcs/` contains job directories with articles and headlines.
- Run `ls working/gcs/jobs/` to confirm structure.

**"ImportError: No module named gavel_ai"**
- Install gavel-ai: `pip install -e ../gavel-ai`

**"Scenario files too large"**
- Reduce `HEADLINE_TARGET`, etc. in `prepare_dataset.py`
- Or manually edit the `.json` files to keep a subset.

## See Also

- `CLAUDE.md` — full project guidelines
- `.cicadas/active/model-upgrade-eval/` — initiative specs (PRD, tech design, approach, tasks, eval-spec)
- `../../gavel-ai/` — evaluation harness framework
