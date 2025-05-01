export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python src/media_lens/scheduler.py --time 07:00 --script ./run_harvest_to_deploy.sh
