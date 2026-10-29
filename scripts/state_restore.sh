#!/usr/bin/env bash
# state 브랜치의 암호화된 DB를 data/giveaways.db 로 복원한다. (STATE_KEY 필요)
set -euo pipefail
mkdir -p data
if git ls-remote --exit-code --heads origin state >/dev/null 2>&1; then
  git fetch origin state --depth=1
  git show FETCH_HEAD:giveaways.db.enc > data/giveaways.db.enc 2>/dev/null || true
fi
if [ -s data/giveaways.db.enc ]; then
  giveaway state decrypt data/giveaways.db.enc data/giveaways.db
fi
