#!/usr/bin/env bash
set -euo pipefail

VERSION=$(hatch version | sed 's/\.dev.*//')
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
