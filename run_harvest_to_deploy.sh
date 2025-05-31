export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python src/media_lens/runner.py run -s harvest extract summarize_daily interpret_weekly format deploy