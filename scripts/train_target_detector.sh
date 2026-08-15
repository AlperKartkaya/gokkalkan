#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATASET="${DATASET:-perception/dataset/generated/yolo_cad_research}"
MODEL="${MODEL:-yolov8s.pt}"
EPOCHS="${EPOCHS:-30}"
IMGSZ="${IMGSZ:-640}"
BATCH="${BATCH:-8}"
DEVICE="${DEVICE:-auto}"
WORKERS="${WORKERS:-0}"
CACHE="${CACHE:-disk}"
NAME="${NAME:-cad-$(date +%Y%m%d-%H%M%S)}"

exec .venv-training/bin/python perception/tools/train_yolo.py \
  --dataset "$DATASET" \
  --model "$MODEL" \
  --epochs "$EPOCHS" \
  --imgsz "$IMGSZ" \
  --batch "$BATCH" \
  --device "$DEVICE" \
  --workers "$WORKERS" \
  --cache "$CACHE" \
  --name "$NAME" \
  --allow-unverified \
  "$@"
