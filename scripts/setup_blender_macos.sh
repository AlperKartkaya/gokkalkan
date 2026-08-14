#!/usr/bin/env bash
set -euo pipefail

VERSION="4.2.1"
ARCH="arm64"
TOOLS_DIR="${1:-.tools}"
INSTALL_DIR="${TOOLS_DIR}/blender-${VERSION}"
APP_PATH="${INSTALL_DIR}/Blender.app"
EXECUTABLE="${APP_PATH}/Contents/MacOS/Blender"
DMG_PATH="${TOOLS_DIR}/downloads/blender-${VERSION}-macos-${ARCH}.dmg"
URL="https://download.blender.org/release/Blender4.2/blender-${VERSION}-macos-${ARCH}.dmg"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "Bu bootstrap yalnız Apple Silicon macOS içindir." >&2
  exit 2
fi

mkdir -p "${INSTALL_DIR}" "${TOOLS_DIR}/downloads"

if [[ ! -x "${EXECUTABLE}" ]]; then
  if [[ ! -f "${DMG_PATH}" ]]; then
    curl --fail --location --show-error "${URL}" --output "${DMG_PATH}"
  fi
  mount_dir="$(mktemp -d /tmp/gokkalkan-blender.XXXXXX)"
  cleanup() {
    hdiutil detach "${mount_dir}" >/dev/null 2>&1 || true
    rmdir "${mount_dir}" >/dev/null 2>&1 || true
  }
  trap cleanup EXIT
  hdiutil attach "${DMG_PATH}" -nobrowse -readonly -mountpoint "${mount_dir}" >/dev/null
  ditto "${mount_dir}/Blender.app" "${APP_PATH}"
  cleanup
  trap - EXIT
fi

# BlenderProc 2.8.0 custom-path discovery expects the numeric resource folder
# at app root, while macOS Blender stores it below Contents/Resources.
if [[ ! -e "${APP_PATH}/4.2" ]]; then
  ln -s "Contents/Resources/4.2" "${APP_PATH}/4.2"
fi

"${EXECUTABLE}" --version | head -n 1
