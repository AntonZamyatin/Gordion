#!/bin/bash
# Run the Gordion backend dev server using the project-local virtualenv.
#
# The venv lives at <repo-root>/.venv (git-ignored). Recreate it with:
#   python3.12 -m venv .venv
#   .venv/bin/pip install -r backend/requirements.txt
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$BACKEND_DIR/.." && pwd)"
VENV="$REPO_ROOT/.venv"

if [[ ! -x "$VENV/bin/uvicorn" ]]; then
  echo "error: venv not found at $VENV (see recreate instructions in this script)" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$BACKEND_DIR"
exec uvicorn app.main:app --reload --port 8000