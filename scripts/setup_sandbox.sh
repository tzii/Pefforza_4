#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --seed .venv
  else
    python3 -m venv .venv
  fi
fi

# Sandboxes need CPU inference, not multi-gigabyte CUDA runtime packages.
.venv/bin/python -m pip install 'torch>=2.3' --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -e '.[dev]'

# Repair environments created before the SB3 extras namespace conflict was removed.
if .venv/bin/python -m pip show pygame-ce >/dev/null 2>&1; then
  .venv/bin/python -m pip uninstall -y pygame-ce
  .venv/bin/python -m pip install --force-reinstall --no-deps 'pygame>=2.5,<3'
fi
