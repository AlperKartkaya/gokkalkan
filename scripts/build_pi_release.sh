#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="${1:-}"

if [[ -z "$OUTPUT" ]]; then
  echo "Usage: scripts/build_pi_release.sh <output-directory>" >&2
  exit 2
fi

OUTPUT="$(mkdir -p "$OUTPUT" && cd "$OUTPUT" && pwd)"
if [[ "$OUTPUT" == "/" || "$OUTPUT" == "$ROOT" ]]; then
  echo "Refusing unsafe release output directory: $OUTPUT" >&2
  exit 2
fi

find "$OUTPUT" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +

# Keep this list explicit. A Pi release must never inherit developer state,
# local virtual environments, synthetic datasets, Blender, or OMX artifacts.
RELEASE_PATHS=(
  README.md
  pyproject.toml
  requirements/backend.lock
  backend
  config
  deploy
  docs
  firmware
  frontend/dist
  perception/assets
  perception/models
  perception/src
  release
  scripts
)

for path in "${RELEASE_PATHS[@]}"; do
  [[ -e "$ROOT/$path" ]] || {
    echo "Required release path missing: $path" >&2
    exit 1
  }
done

(
  cd "$ROOT"
  rsync -aR \
    --exclude '__pycache__/' \
    --exclude '*.py[co]' \
    --exclude '*.egg-info/' \
    --exclude '.DS_Store' \
    --exclude 'perception/models/*.hef' \
    "${RELEASE_PATHS[@]}" \
    "$OUTPUT/"
)

[[ -f "$OUTPUT/frontend/dist/index.html" ]] || {
  echo "Release missing frontend/dist/index.html" >&2
  exit 1
}
[[ -f "$OUTPUT/scripts/bootstrap_pi.sh" ]] || {
  echo "Release missing scripts/bootstrap_pi.sh" >&2
  exit 1
}

echo "Pi release prepared: $OUTPUT ($(du -sh "$OUTPUT" | awk '{print $1}'))"
