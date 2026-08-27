#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${1:-}" ]]; then
  VERSION="$1"
else
  VERSION=$(uv run hatch version | sed 's/\.dev.*//')
fi
echo "🏷 Releasing version: $VERSION"

# check changelog date for this version
uv run python scripts/check_changelog_date.py "$VERSION"

if ! git diff --quiet HEAD; then
  echo "❌ ERROR: Working directory is dirty. Commit your changes through a PR."
  exit 1
fi

# Create and push tag only
git tag "v$VERSION" -m "Release v$VERSION"
git push origin "v$VERSION"
echo "✅ Tag v$VERSION pushed successfully."
