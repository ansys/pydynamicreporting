#!/usr/bin/env bash
set -euo pipefail

if [[ -n "$(git status --porcelain)" ]]; then
  echo "❌ ERROR: Working directory is dirty, including untracked files. Commit or remove changes through a PR."
  exit 1
fi

command -v gh > /dev/null 2>&1 || {
  echo "❌ ERROR: GitHub CLI (gh) is required to verify the release commit."
  exit 1
}

git fetch origin --prune --tags

BRANCH=$(git branch --show-current)
if [[ "$BRANCH" != "main" && "$BRANCH" != stable/* ]]; then
  echo "❌ ERROR: Releases must be tagged from main or a stable/* maintenance branch, not '$BRANCH'."
  exit 1
fi

if ! UPSTREAM=$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null); then
  echo "❌ ERROR: Branch '$BRANCH' does not have an upstream branch."
  exit 1
fi

EXPECTED_UPSTREAM="origin/$BRANCH"
if [[ "$UPSTREAM" != "$EXPECTED_UPSTREAM" ]]; then
  echo "❌ ERROR: Branch '$BRANCH' must track '$EXPECTED_UPSTREAM', not '$UPSTREAM'."
  exit 1
fi

HEAD_COMMIT=$(git rev-parse HEAD)
UPSTREAM_COMMIT=$(git rev-parse "$UPSTREAM")
if [[ "$HEAD_COMMIT" != "$UPSTREAM_COMMIT" ]]; then
  echo "❌ ERROR: HEAD does not exactly match '$UPSTREAM'. Use a fresh, up-to-date checkout."
  exit 1
fi

if [[ -n "${1:-}" ]]; then
  VERSION="$1"
else
  VERSION=$(uv run hatch version | sed 's/\.dev.*//')
fi
echo "🏷 Releasing version: $VERSION"

TAG="v$VERSION"
TAG_PATTERN='^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(rc(0|[1-9][0-9]*))?$'
if [[ ! "$TAG" =~ $TAG_PATTERN ]]; then
  echo "❌ ERROR: Unsupported release tag '$TAG'. Expected vMAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCHrcN with no leading zeroes."
  exit 1
fi

# check changelog date for this version
uv run python scripts/check_changelog_date.py "$VERSION"

if git show-ref --verify --quiet "refs/tags/$TAG"; then
  echo "❌ ERROR: Tag '$TAG' already exists."
  exit 1
fi

CI_RUNS_ENDPOINT="repos/{owner}/{repo}/actions/workflows/ci_cd.yml/runs?head_sha=$HEAD_COMMIT&event=push&per_page=1"
CI_RUN=$(gh api "$CI_RUNS_ENDPOINT" --jq '(.workflow_runs[0] // empty) | [.status, .conclusion, .head_branch, .html_url] | @tsv')
if [[ -z "$CI_RUN" ]]; then
  echo "❌ ERROR: No CI-CD push run exists for commit '$HEAD_COMMIT'."
  exit 1
fi

IFS=$'\t' read -r CI_STATUS CI_CONCLUSION CI_BRANCH CI_URL <<< "$CI_RUN"
if [[ "$CI_BRANCH" != "$BRANCH" || "$CI_STATUS" != "completed" || "$CI_CONCLUSION" != "success" ]]; then
  echo "❌ ERROR: CI-CD must complete successfully for '$BRANCH' at '$HEAD_COMMIT'."
  echo "CI run: $CI_URL (branch=$CI_BRANCH, status=$CI_STATUS, conclusion=$CI_CONCLUSION)"
  exit 1
fi

# Create and push tag only
git tag "$TAG" -m "Release $TAG"
git push origin "$TAG"
echo "✅ Tag $TAG pushed successfully."
