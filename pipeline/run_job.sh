#!/usr/bin/env bash
# Render cron job: refresh the data, then commit it back to GitHub so the
# static site redeploys. Needs env vars GITHUB_REPO ("owner/repo") and
# GITHUB_TOKEN (fine-grained token with Contents: read & write on that repo).
set -euo pipefail

: "${GITHUB_REPO:?GITHUB_REPO not set}"
: "${GITHUB_TOKEN:?GITHUB_TOKEN not set}"

WORK="$(mktemp -d)"
git clone --quiet --depth 1 "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" "$WORK/repo"
cd "$WORK/repo"

pip install --quiet -r requirements.txt
python -m pipeline.build

git config user.name "spending-dashboard-bot"
git config user.email "spending-dashboard-bot@users.noreply.github.com"
git add data web/data
if git diff --cached --quiet; then
  echo "No data changes."
  exit 0
fi
git commit --quiet -m "Refresh spending data"
git push --quiet origin HEAD
echo "Data refreshed and pushed."
