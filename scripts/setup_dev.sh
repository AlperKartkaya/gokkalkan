#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade "pip==25.1.1" "setuptools==75.6.0" "wheel==0.45.1"
.venv/bin/python -m pip install -r requirements/dev.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
npm --prefix frontend ci

echo "Development environment ready."
echo "  npm run dev:check"
echo "  npm run desktop"
echo "  npm run doctor"
