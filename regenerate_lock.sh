#!/usr/bin/env bash
# Regenerate uv.lock using the standard PyPI index.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

echo "Removing existing uv.lock ..."
rm -f uv.lock

echo "Regenerating uv.lock with PyPI Simple index ..."
UV_INDEX_URL="https://pypi.org/simple" uv lock

echo "Done. uv.lock regenerated."
