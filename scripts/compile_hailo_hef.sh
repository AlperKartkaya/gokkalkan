#!/usr/bin/env bash
# Compile the exported research detector on an x86_64 Hailo DFC/Model-Zoo host.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ONNX="$(realpath "${1:-$ROOT/artifacts/hailo/target_detector.onnx}")"
CALIBRATION="$(realpath "${2:-$ROOT/perception/dataset/generated/yolo_cad_research/images/train}")"
OUTPUT="$(realpath -m "${3:-$ROOT/artifacts/hailo/target_detector.hef}")"

command -v hailomz >/dev/null || {
  echo "hailomz bulunamadı. Bu komut Pi'de değil, Hailo Dataflow Compiler kurulu x86_64 Linux makinede çalışır." >&2
  exit 2
}
[[ -f "$ONNX" ]] || { echo "ONNX bulunamadı: $ONNX" >&2; exit 2; }
[[ -d "$CALIBRATION" ]] || { echo "Kalibrasyon görüntü dizini bulunamadı: $CALIBRATION" >&2; exit 2; }

MODEL_ZOO_ROOT="${HAILO_MODEL_ZOO:-}"
if [[ -z "$MODEL_ZOO_ROOT" ]]; then
  MODEL_ZOO_ROOT="$(python3 - <<'PY'
import importlib.util
spec = importlib.util.find_spec('hailo_model_zoo')
print('' if spec is None else spec.submodule_search_locations[0])
PY
)"
fi
YAML="${HAILO_YOLOV8S_YAML:-$MODEL_ZOO_ROOT/cfg/networks/yolov8s.yaml}"
[[ -f "$YAML" ]] || { echo "yolov8s Model Zoo YAML bulunamadı: $YAML" >&2; exit 2; }

mkdir -p "$(dirname "$OUTPUT")"
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/gokkalkan-hailo.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

# Model Zoo writes the HEF under the current directory. Keep that output away
# from the checkout, then copy only the deterministic artifact into artifacts/.
(
  cd "$WORKDIR"
  hailomz compile \
    --ckpt "$ONNX" \
    --calib-path "$CALIBRATION" \
    --yaml "$YAML" \
    --classes 7 \
    --hw-arch hailo8
)
HEF="$(find "$WORKDIR" -type f -name '*.hef' | head -n 1)"
[[ -n "$HEF" ]] || { echo "hailomz bir .hef üretmedi" >&2; exit 1; }
install -m 0644 "$HEF" "$OUTPUT"
sha256sum "$OUTPUT"
echo "HEF hazır: $OUTPUT"
