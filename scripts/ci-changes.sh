#!/usr/bin/env bash
set -euo pipefail
# Fail open to doing the work when history or the comparison ref is unavailable.
if [[ "${CIRCLE_BRANCH:-}" == "main" ]]; then
  base=$(git rev-parse HEAD^ 2>/dev/null) || exit 0
else
  git fetch origin main --no-tags || exit 0
  base=$(git merge-base HEAD origin/main) || exit 0
fi
changed=$(git diff --name-only "$base" HEAD) || exit 0
if [[ -n "$changed" ]] && ! printf '%s\n' "$changed" | \
  grep -qvE '^(docs/.*|README\.md|LICENSE|.*\.md)$'; then
  echo "Documentation-only change: skipping image build, tests, and publication."
  circleci-agent step halt
fi
