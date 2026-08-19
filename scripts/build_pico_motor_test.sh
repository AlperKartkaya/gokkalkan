#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SDK_PATH="${PICO_SDK_PATH:-$ROOT/.tools/pico-sdk}"
BUILD_DIR="${GOKKALKAN_PICO_TEST_BUILD_DIR:-$ROOT/build/firmware-pico-motor-test}"
if [[ ! -f "$SDK_PATH/external/pico_sdk_import.cmake" ]]; then
  echo "Pico SDK bulunamadı: $SDK_PATH" >&2
  exit 2
fi
export PICO_SDK_PATH="$SDK_PATH"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cmake -S "$ROOT/firmware/pico" -B "$BUILD_DIR" -G Ninja \
  -DGOKKALKAN_BUILD_MOTOR_TEST=ON
cmake --build "$BUILD_DIR" --target gokkalkan_motor_test
echo "UF2 hazır: $BUILD_DIR/gokkalkan_motor_test.uf2"
