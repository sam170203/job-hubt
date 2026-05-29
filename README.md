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

## Install the `job-hunt` terminal command

```bash
scripts/install_command.sh
source ~/.zshrc
job-hunt
```

This adds an alias to `~/.zshrc` so you can launch the dashboard from anywhere with `job-hunt`.

## Schedule the daily scrape

Add this to your crontab (`crontab -e`):

```cron
0 9 * * * cd /Users/saksham/creative-task/job-hunt && scripts/run_scrapers.sh >> data/cron.log 2>&1
```

Logs land in `data/cron.log`.

**Note:** The user installs the cron line manually — the codebase never touches the system crontab.

## Gmail integration (one-time setup, optional)

The Gmail scraper aggregates recruiter outreach and job-alert digests from your inbox.

**One-time setup:**

1. Go to https://console.cloud.google.com and create a project.
2. Enable the Gmail API.
3. Create an OAuth 2.0 Client ID (type: **Desktop App**).
4. Download the `client_secret_*.json` file.
5. Set in `.env`:
   ```bash
   GMAIL_CLIENT_SECRETS_PATH=/path/to/client_secret_xxx.json
   ```
6. Run:
   ```bash
   uv run python scripts/setup_gmail.py
   ```
   Browser opens; sign in and grant **read-only** Gmail access. Token is saved to `data/.gmail_token.json` (gitignored).

After setup, the daily cron will include Gmail in its scrape.
