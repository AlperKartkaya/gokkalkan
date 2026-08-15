#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BATCH_ROOT="${BATCH_ROOT:-perception/synthetic/generated/render_batches/cad_pilot_378}"
OUTPUT="${OUTPUT:-perception/dataset/generated/yolo_cad_research}"
WORKERS="${WORKERS:-0}"

exec .venv-synthetic/bin/python perception/tools/dataset_pipeline.py ingest-cad \
  --batch-root "$BATCH_ROOT" \
  --output "$OUTPUT" \
  --workers "$WORKERS" \
  "$@"
