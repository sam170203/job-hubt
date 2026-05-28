#!/usr/bin/env bash
# Daily scraper run. Invoked by cron at 09:00 IST.
# More scrapers added in Plan 2.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

UV="$(command -v uv || echo /opt/homebrew/bin/uv)"

echo "[$(date -Iseconds)] === run_scrapers.sh start ==="

"$UV" run python - <<'PY'
from datetime import datetime
from job_hunt.db import init_db
from job_hunt.scrapers.hn_hiring import HNHiringScraper
from job_hunt.scrapers.base import write_to_staging
from job_hunt.pipeline.run import run_pipeline

init_db()
rows = HNHiringScraper().run()
inserted = write_to_staging(rows, scraped_at=datetime.utcnow())
print(f"HN: scraped {len(rows)}, staged {inserted}")
stats = run_pipeline()
print(f"Pipeline: promoted={stats.promoted}, duplicates={stats.duplicates}, "
      f"unknown_source={stats.skipped_unknown_source}")
PY

echo "[$(date -Iseconds)] === run_scrapers.sh done ==="
