#!/usr/bin/env bash
# Daily scraper run — cron invokes this at 09:00 IST.
#
# Runs every scraper, writes to staging, then runs the pipeline once.
# Each scraper is best-effort: a single source failing does not stop the others.

set -uo pipefail   # NOTE: not `-e`; we want partial failure tolerance.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

UV="$(command -v uv || echo /opt/homebrew/bin/uv)"

echo "[$(date -Iseconds)] === run_scrapers.sh start ==="

"$UV" run python - <<'PY'
from datetime import datetime
import traceback

from job_hunt.db import init_db
from job_hunt.scrapers.base import write_to_staging
from job_hunt.scrapers.hn_hiring import HNHiringScraper
from job_hunt.scrapers.careers_pages import CareersPagesScraper
from job_hunt.scrapers.wellfound import WellfoundScraper
from job_hunt.scrapers.x_search import XSearchScraper
from job_hunt.scrapers.gmail_inbox import GmailInboxScraper
from job_hunt.pipeline.run import run_pipeline


SCRAPERS = [
    ("hn",        HNHiringScraper),
    ("careers",   CareersPagesScraper),
    ("wellfound", WellfoundScraper),
    ("x",         XSearchScraper),
    ("gmail",     GmailInboxScraper),
]


init_db()
ts = datetime.utcnow()
total_scraped = 0
total_staged = 0

for name, cls in SCRAPERS:
    t0 = datetime.utcnow()
    try:
        rows = cls().run()
    except Exception as exc:
        print(f"[{name}] ERROR: {exc.__class__.__name__}: {exc}")
        traceback.print_exc()
        continue
    staged = write_to_staging(rows, scraped_at=ts)
    total_scraped += len(rows)
    total_staged += staged
    secs = (datetime.utcnow() - t0).total_seconds()
    print(f"[{name}] scraped={len(rows)} staged={staged} took={secs:.1f}s")

print(f"--- total: scraped={total_scraped} staged={total_staged} ---")

t0 = datetime.utcnow()
stats = run_pipeline()
secs = (datetime.utcnow() - t0).total_seconds()
print(f"[pipeline] promoted={stats.promoted} duplicates={stats.duplicates} "
      f"unknown_source={stats.skipped_unknown_source} took={secs:.1f}s")
PY

echo "[$(date -Iseconds)] === run_scrapers.sh done ==="
