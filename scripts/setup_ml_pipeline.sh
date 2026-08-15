#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v uv >/dev/null 2>&1 || {
  echo "uv bulunamadı: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 2
}

ensure_env() {
  local path="$1"
  local lock="$2"
  if [[ ! -x "$path/bin/python" ]]; then
    uv venv "$path" --python 3.11
  fi
  uv pip install --python "$path/bin/python" -r "$lock"
}

ensure_env .venv-perception requirements/perception-dev.lock
ensure_env .venv-synthetic requirements/synthetic-render.lock
ensure_env .venv-training requirements/training-dev.lock

if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  bash scripts/setup_blender_macos.sh
else
  echo "Blender otomatik kurulmadı. Render sırasında GOKKALKAN_BLENDER yolunu belirtin."
fi

echo "ML/sentetik veri ortamları hazır."
echo "  ./scripts/render_cad_dataset.sh"
echo "  ./scripts/ingest_cad_dataset.sh"
echo "  ./scripts/train_target_detector.sh"
echo "  ./scripts/predict_target_val.sh"
