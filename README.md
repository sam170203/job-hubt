# job-hunt

Semi-automated personal job-hunt system. Local-first. Python + SQLite + Streamlit.

See `docs/superpowers/specs/2026-05-26-job-hunt-system-design.md` for the full design.

## Quick start

```bash
uv sync
uv run python -c "from job_hunt.db import init_db; init_db()"
uv run streamlit run src/job_hunt/dashboard/app.py
```

## Daily scrape

```bash
scripts/run_scrapers.sh
```

## Tests

```bash
uv run pytest
```

## Schedule the daily scrape

Add this to your crontab (`crontab -e`):

```cron
0 9 * * * cd /Users/saksham/creative-task/job-hunt && scripts/run_scrapers.sh >> data/cron.log 2>&1
```

Logs land in `data/cron.log`.

**Note:** The user installs the cron line manually — the codebase never touches the system crontab.
