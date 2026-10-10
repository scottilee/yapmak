#!/usr/bin/env bash
# Compatibility entry point; shared runner owns waits, health checks, retries and logging.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
source .env
set +a
exec .venv/bin/python -u scripts/run_batch.py --config scripts/batches/batch_v17.json "$@"
