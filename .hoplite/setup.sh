#!/usr/bin/env bash
# Hoplite sandbox setup for Pefforza (AGENTS.md "Setup commands").
# Creates the project venv and installs pefforza with dev tooling,
# idempotently so re-running it on an existing sandbox is cheap.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi

.venv/bin/pip install -q -e ".[dev]"

# The default linux torch wheel pulls ~4 GB of NVIDIA/CUDA packages that the
# CPU-bound test suite never uses and that can exceed the sandbox disk quota;
# swap in the CPU wheel (idempotent: no-op once torch.version.cuda is None).
if .venv/bin/python -c "import sys, torch; sys.exit(0 if torch.version.cuda else 1)" 2>/dev/null; then
    NVIDIA_PKGS=$(.venv/bin/pip list 2>/dev/null | grep -i "^nvidia-" | awk '{print $1}')
    .venv/bin/pip uninstall -y -q torch triton $NVIDIA_PKGS || true
    .venv/bin/pip install -q torch --index-url https://download.pytorch.org/whl/cpu
fi

# Fail fast on a broken install instead of at first test invocation.
.venv/bin/python -c "import pefforza"
