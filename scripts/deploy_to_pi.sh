#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_HOST=""
IDENTITY=""
SKIP_BUILD=0
HEF_PATH=""
RUNNER_FACTORY=""
REMOTE_RELEASE="/tmp/gokkalkan-release"
LOCAL_RELEASE=""

cleanup() {
  if [[ -n "$LOCAL_RELEASE" && -d "$LOCAL_RELEASE" ]]; then
    rm -rf "$LOCAL_RELEASE"
  fi
}
trap cleanup EXIT

usage() {
  cat <<'EOF'
Usage: scripts/deploy_to_pi.sh --host pi@<adres> [--identity ~/.ssh/id_ed25519] [--skip-build]
       [--hef ./target_detector.hef --runner-factory gokkalkan_hailo_runtime:create_batch_runner]

Builds the frontend locally, copies a clean release tree to the Raspberry Pi,
runs the idempotent Pi bootstrap, and verifies persistent systemd services.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) PI_HOST="${2:?--host value missing}"; shift 2 ;;
    --identity) IDENTITY="${2:?--identity value missing}"; shift 2 ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --hef) HEF_PATH="${2:?--hef value missing}"; shift 2 ;;
    --runner-factory) RUNNER_FACTORY="${2:?--runner-factory value missing}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$PI_HOST" ]] || { usage >&2; exit 2; }
if [[ -n "$HEF_PATH" || -n "$RUNNER_FACTORY" ]]; then
  [[ -n "$HEF_PATH" && -n "$RUNNER_FACTORY" ]] || { echo "--hef and --runner-factory must be supplied together" >&2; exit 2; }
  [[ -f "$HEF_PATH" ]] || { echo "HEF not found: $HEF_PATH" >&2; exit 2; }
  [[ "$RUNNER_FACTORY" =~ ^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$ ]] || { echo "invalid runner factory; expected python.module:create_function" >&2; exit 2; }
fi
command -v ssh >/dev/null || { echo "ssh not found" >&2; exit 1; }
command -v rsync >/dev/null || { echo "rsync not found" >&2; exit 1; }

SSH_ARGS=(-o BatchMode=yes -o ConnectTimeout=10)
if [[ -n "$IDENTITY" ]]; then
  SSH_ARGS+=(-i "$IDENTITY")
fi

python3 "$ROOT/scripts/verify_pi_manifest.py" --manifest-only
if [[ "$SKIP_BUILD" -eq 0 ]]; then
  npm --prefix "$ROOT/frontend" ci
  npm --prefix "$ROOT/frontend" run build
fi
[[ -f "$ROOT/frontend/dist/index.html" ]] || {
  echo "frontend/dist missing; run without --skip-build first" >&2
  exit 1
}

LOCAL_RELEASE="$(mktemp -d "${TMPDIR:-/tmp}/gokkalkan-pi-release.XXXXXX")"
bash "$ROOT/scripts/build_pi_release.sh" "$LOCAL_RELEASE"

# Keep the remote staging directory between deploys so rsync can transfer only
# changed files. --delete still removes files that no longer belong to release.
ssh "${SSH_ARGS[@]}" "$PI_HOST" "mkdir -p '$REMOTE_RELEASE'"
rsync -az --delete \
  --exclude 'perception/models/*.hef' \
  -e "ssh ${SSH_ARGS[*]}" "$LOCAL_RELEASE/" "$PI_HOST:$REMOTE_RELEASE/"

if [[ -n "$HEF_PATH" ]]; then
  rsync -az -e "ssh ${SSH_ARGS[*]}" "$HEF_PATH" "$PI_HOST:$REMOTE_RELEASE/perception/models/target_detector.hef"
fi

REMOTE_SETUP="cd '$REMOTE_RELEASE' && sudo bash scripts/bootstrap_pi.sh --apply"
if [[ -n "$HEF_PATH" ]]; then
  REMOTE_SETUP+=" && printf 'GOKKALKAN_HAILO_BATCH_RUNNER_FACTORY=%s\\n' '$RUNNER_FACTORY' | sudo tee /etc/gokkalkan/perception.env >/dev/null && sudo chmod 0640 /etc/gokkalkan/perception.env && sudo touch /etc/gokkalkan/enable-perception"
fi

ssh -t "${SSH_ARGS[@]}" "$PI_HOST" \
  "$REMOTE_SETUP && \
   sudo systemctl enable gokkalkan.target && \
   sudo systemctl restart gokkalkan.target && \
   curl --fail --silent http://127.0.0.1:8088/health >/dev/null && \
   curl --fail --silent http://127.0.0.1:4173/healthz >/dev/null && \
   systemctl is-enabled gokkalkan.target && systemctl is-active gokkalkan.target"

echo "Deploy complete. Pi services persist after SSH disconnect and reboot."
echo "Operator tunnel: ssh -N -L 4173:127.0.0.1:4173 -L 8088:127.0.0.1:8088 -L 8090:127.0.0.1:8090 $PI_HOST"
