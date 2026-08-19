#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; HOST=""; IDENTITY=""; PREPARE=0
while (($#)); do case "$1" in
  --host) HOST="$2"; shift 2;; --identity) IDENTITY="$2"; shift 2;;
  --prepare) PREPARE=1; shift;; *) echo "Bilinmeyen argüman: $1" >&2; exit 2;; esac; done
[[ -n "$HOST" ]] || { echo "Kullanım: $0 --host user@pi [--identity key] [--prepare]" >&2; exit 2; }
SSH=(ssh); RSYNC_SSH="ssh"
if [[ -n "$IDENTITY" ]]; then SSH+=(-i "$IDENTITY"); RSYNC_SSH="ssh -i $IDENTITY"; fi
REMOTE=/tmp/gokkalkan-pico-motor-test
SDK_REMOTE='~/.cache/gokkalkan/pico-sdk-2.1.1'
"${SSH[@]}" "$HOST" "rm -rf '$REMOTE' && mkdir -p '$REMOTE/firmware' '$REMOTE/scripts'"
rsync -az -e "$RSYNC_SSH" "$ROOT/firmware/pico/" "$HOST:$REMOTE/firmware/pico/"
rsync -az -e "$RSYNC_SSH" "$ROOT/scripts/build_pico_motor_test.sh" "$ROOT/scripts/pico_motor_test.py" "$HOST:$REMOTE/scripts/"
if ((PREPARE)); then
  "${SSH[@]}" -t "$HOST" "sudo apt-get update && sudo apt-get install -y cmake ninja-build gcc-arm-none-eabi libnewlib-arm-none-eabi git picotool && mkdir -p ~/.cache/gokkalkan && if [[ ! -f $SDK_REMOTE/external/pico_sdk_import.cmake ]]; then git clone --branch 2.1.1 --depth 1 --recurse-submodules https://github.com/raspberrypi/pico-sdk.git $SDK_REMOTE; fi"
fi
"${SSH[@]}" "$HOST" "test -f $SDK_REMOTE/external/pico_sdk_import.cmake || { echo 'Pico SDK yok; --prepare ile çalıştırın' >&2; exit 2; }; cd '$REMOTE' && chmod +x scripts/* && PICO_SDK_PATH=$SDK_REMOTE bash scripts/build_pico_motor_test.sh"
"${SSH[@]}" -t "$HOST" "sudo picotool load -f -x '$REMOTE/build/firmware-pico-motor-test/gokkalkan_motor_test.uf2'"
echo "Yüklendi. Test: ssh ${IDENTITY:+-i $IDENTITY }$HOST 'python3 $REMOTE/scripts/pico_motor_test.py --driver 1 --direction CW --steps 200 --hz 100'"
