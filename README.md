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
