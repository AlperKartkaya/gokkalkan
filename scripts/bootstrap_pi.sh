#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
elif [[ "${1:-}" != "--check" ]]; then
  echo "Usage: sudo bash scripts/bootstrap_pi.sh --check|--apply" >&2
  exit 2
fi

python3 "$REPO_ROOT/scripts/verify_pi_manifest.py" --manifest-only
if [[ "$APPLY" -eq 0 ]]; then
  echo "Manifest valid. --apply was not requested; host was not modified."
  exit 0
fi
if [[ "$(id -u)" -ne 0 ]]; then
  echo "--apply must run as root" >&2
  exit 1
fi
if [[ ! -f "$REPO_ROOT/frontend/dist/index.html" ]]; then
  echo "frontend/dist missing. Build the deploy artifact with: npm ci && npm run build" >&2
  exit 1
fi

mapfile -t APT_PACKAGES < <(
  python3 - "$REPO_ROOT/deploy/pi/manifest.toml" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    for package in tomllib.load(handle)["packages"]["apt"]:
        print(package)
PY
)

install -d -o root -g root -m 0755 /var/lib/gokkalkan
APT_FINGERPRINT="$({
  cat "$REPO_ROOT/deploy/pi/manifest.toml"
  printf '%s\n' "${APT_PACKAGES[@]}"
} | sha256sum | awk '{print $1}')"
APT_MARKER="/var/lib/gokkalkan/apt-bootstrap.sha256"

APT_MISSING=0
for package in "${APT_PACKAGES[@]}"; do
  dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -qx 'install ok installed' || {
    APT_MISSING=1
    break
  }
done

if [[ "$APT_MISSING" -eq 1 || ! -f "$APT_MARKER" || "$(cat "$APT_MARKER")" != "$APT_FINGERPRINT" ]]; then
  echo "Pi system dependencies changed or are missing; running apt."
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${APT_PACKAGES[@]}"
  printf '%s\n' "$APT_FINGERPRINT" > "$APT_MARKER"
else
  echo "Pi system dependencies unchanged; skipping apt."
fi

if ! id gokkalkan >/dev/null 2>&1; then
  useradd --create-home --system --shell /usr/sbin/nologin --user-group gokkalkan
fi
for group in dialout gpio render video; do
  getent group "$group" >/dev/null || groupadd --system "$group"
  usermod -aG "$group" gokkalkan
done

install -d -o gokkalkan -g gokkalkan /opt/gokkalkan /var/lib/gokkalkan/telemetry
install -d -o root -g gokkalkan -m 0750 /etc/gokkalkan
if [[ "$(realpath "$REPO_ROOT")" != "/opt/gokkalkan" ]]; then
  rsync -a --delete \
    --exclude 'perception/models/*.hef' \
    --exclude '.git/' --exclude '.venv/' --exclude 'node_modules/' \
    --exclude 'telemetry_data/' \
    "$REPO_ROOT/" /opt/gokkalkan/
fi

PYTHON_FINGERPRINT="$({
  python3 -VV
  cat /opt/gokkalkan/requirements/backend.lock
  cat /opt/gokkalkan/pyproject.toml
} | sha256sum | awk '{print $1}')"
PYTHON_MARKER="/var/lib/gokkalkan/python-dependencies.sha256"

if [[ ! -x /opt/gokkalkan/.venv/bin/python || ! -f "$PYTHON_MARKER" || "$(cat "$PYTHON_MARKER")" != "$PYTHON_FINGERPRINT" ]]; then
  echo "Python dependencies changed or are missing; updating virtual environment."
  python3 -m venv --system-site-packages /opt/gokkalkan/.venv
  /opt/gokkalkan/.venv/bin/python -m pip install \
    "pip==25.1.1" "setuptools==75.6.0" "wheel==0.45.1"
  /opt/gokkalkan/.venv/bin/python -m pip install \
    -r /opt/gokkalkan/requirements/backend.lock
  printf '%s\n' "$PYTHON_FINGERPRINT" > "$PYTHON_MARKER"
else
  echo "Python dependencies unchanged; skipping dependency install."
fi

# Application source changes on every release, even when dependencies do not.
/opt/gokkalkan/.venv/bin/python -m pip install \
  --no-deps --no-build-isolation /opt/gokkalkan

install -o root -g gokkalkan -m 0640 \
  /opt/gokkalkan/config/runtime/pi-sim.toml /etc/gokkalkan/runtime.toml
install -d -o root -g gokkalkan -m 0750 /etc/gokkalkan/calibration
cp -a /opt/gokkalkan/config/calibration/. /etc/gokkalkan/calibration/
chown -R root:gokkalkan /etc/gokkalkan/calibration
chmod -R u=rwX,g=rX,o= /etc/gokkalkan/calibration
install -o root -g root -m 0644 /opt/gokkalkan/deploy/systemd/*.service /etc/systemd/system/
install -o root -g root -m 0644 /opt/gokkalkan/deploy/systemd/gokkalkan.target /etc/systemd/system/

dpkg-query -W -f='${Package}==${Version}\n' \
  > /var/lib/gokkalkan/installed-packages.lock
chown gokkalkan:gokkalkan /var/lib/gokkalkan/installed-packages.lock

systemctl daemon-reload
systemctl enable --now gokkalkan.target
/opt/gokkalkan/.venv/bin/gokkalkan doctor \
  --config /etc/gokkalkan/runtime.toml
python3 /opt/gokkalkan/scripts/verify_pi_manifest.py --host

echo "Pi bootstrap complete in SIM. LIVE remains disabled."
