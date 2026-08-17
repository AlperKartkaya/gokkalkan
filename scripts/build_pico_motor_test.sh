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
cmake -S "$ROOT/firmware/pico" -B "$BUILD_DIR" -G Ninja \
  -DGOKKALKAN_BUILD_MOTOR_TEST=ON \
  -DGOKKALKAN_TEST_STEP_PIN="${GOKKALKAN_TEST_STEP_PIN:-2}" \
  -DGOKKALKAN_TEST_DIR_PIN="${GOKKALKAN_TEST_DIR_PIN:-3}" \
  -DGOKKALKAN_TEST_ENABLE_PIN="${GOKKALKAN_TEST_ENABLE_PIN:-4}" \
  -DGOKKALKAN_TEST_SIGNAL_ACTIVE_HIGH="${GOKKALKAN_TEST_SIGNAL_ACTIVE_HIGH:-1}"
cmake --build "$BUILD_DIR" --target gokkalkan_motor_test
echo "UF2 hazır: $BUILD_DIR/gokkalkan_motor_test.uf2"
