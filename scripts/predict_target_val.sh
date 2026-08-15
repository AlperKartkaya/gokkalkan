#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATASET="${DATASET:-perception/dataset/generated/yolo_cad_research}"
SOURCE="${SOURCE:-$DATASET/images/val}"
PROJECT="${PROJECT:-perception/dataset/model_runs/predictions}"
IMGSZ="${IMGSZ:-640}"
CONF="${CONF:-0.25}"
BATCH="${BATCH:-16}"
DEVICE="${DEVICE:-auto}"

absolute_path() {
  if [[ "$1" = /* ]]; then
    printf '%s\n' "$1"
  else
    printf '%s/%s\n' "$ROOT" "$1"
  fi
}

SOURCE="$(absolute_path "$SOURCE")"
PROJECT="$(absolute_path "$PROJECT")"

if [[ -z "${WEIGHTS:-}" ]]; then
  WEIGHTS="$(.venv-training/bin/python - <<'PY'
from pathlib import Path
weights = sorted(
    Path("perception/dataset/model_runs").glob("*/weights/best.pt"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
)
if not weights:
    raise SystemExit("best.pt bulunamadı; önce training çalıştırın")
print(weights[0])
PY
)"
fi
WEIGHTS="$(absolute_path "$WEIGHTS")"

if [[ "$DEVICE" == "auto" ]]; then
  DEVICE="$(.venv-training/bin/python - <<'PY'
import torch
if torch.cuda.is_available():
    print(0)
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    print("mps")
else:
    print("cpu")
PY
)"
fi

NAME="${NAME:-$(basename "$(dirname "$(dirname "$WEIGHTS")")")-val}"
exec .venv-training/bin/yolo predict \
  model="$WEIGHTS" \
  source="$SOURCE" \
  imgsz="$IMGSZ" \
  conf="$CONF" \
  batch="$BATCH" \
  device="$DEVICE" \
  save=True \
  project="$PROJECT" \
  name="$NAME" \
  "$@"
