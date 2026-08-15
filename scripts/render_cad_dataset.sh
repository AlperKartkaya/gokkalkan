#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PLAN="${PLAN:-perception/synthetic/generated/render_plans/cad_pilot_378.json}"
OUTPUT="${OUTPUT:-perception/synthetic/generated/render_batches/cad_pilot_378}"
WORKERS="${WORKERS:-0}"
RENDER_DEVICE="${RENDER_DEVICE:-auto}"
RETRIES="${RETRIES:-2}"
RENDER_WIDTH="${RENDER_WIDTH:-2304}"
RENDER_HEIGHT="${RENDER_HEIGHT:-1296}"

exec .venv-synthetic/bin/python \
  perception/synthetic/tools/render_plan_batch.py \
  --plan "$PLAN" \
  --output "$OUTPUT" \
  --workers "$WORKERS" \
  --render-device "$RENDER_DEVICE" \
  --retries "$RETRIES" \
  --width "$RENDER_WIDTH" \
  --height "$RENDER_HEIGHT" \
  "$@"
