#!/bin/bash
set -e

# Run tests with coverage reporting on the media_lens package
# Coverage reporting is included but not enforced (currently at 48.92%)
# TODO: Improve test coverage to meet 80% threshold
uv run pytest --cov=src/media_lens --cov-report=term-missing
