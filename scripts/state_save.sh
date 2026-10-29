#!/usr/bin/env bash
# data/giveaways.db 를 암호화해 state 브랜치(히스토리 없이 1커밋)로 올린다. (STATE_KEY, GH_TOKEN 필요)
set -euo pipefail
giveaway state encrypt data/giveaways.db data/giveaways.db.enc
d=$(mktemp -d)
cp data/giveaways.db.enc "$d/"
cd "$d"
git init -q -b state
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add giveaways.db.enc
git commit -q -m "state $(date -u +%FT%TZ)"
git push -f "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" state
