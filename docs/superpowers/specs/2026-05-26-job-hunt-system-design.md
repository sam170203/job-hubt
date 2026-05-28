# Job-Hunt System — Design Spec

**Date:** 2026-05-26
**Owner:** Saksham Mudgal Sharma
**Status:** Approved (brainstorming phase complete; pending user spec review before planning)

---

## 1. Goal

Build a personal, semi-automated job-hunt system that:

1. **Discovers** fresh, relevant opportunities daily from multiple sources without manual checking.
2. **Tracks** every application, reply, and interview event in a single source of truth.
3. **Analyzes** outcomes weekly to surface concrete reasons applications are failing (resume gaps, mis-targeted companies, weak channels) so the next week's effort is sharper than the last.

The system is built for a single user (Saksham), running locally on macOS, optimized for an India-based final-year B.Tech student targeting a mix of (1) Indian startups, (2) AI/ML roles at startups and foundation labs, and (3) FAANG/big-tech India offices.

This system is itself a portfolio artifact — components like the dashboard, RAG-style JD analyzer, and scrapers are intentionally designed to be demoable.

## 2. Non-Goals

- **Not** a fully automated apply-bot. Auto-applying gets accounts banned and produces template applications. Humans review and apply.
- **Not** a multi-tenant SaaS. Single user, local-first, no auth layer.
- **Not** a CRM replacement. Contact tracking is lightweight (just enough to follow up).
- **No cloud deployment** in the initial build. Cron + SQLite on the local Mac is sufficient.

## 3. Sources (locked)

| Source | Role | Method |
|---|---|---|
| **Target company careers pages (D)** | Highest signal | Playwright; one adapter per company; 30–50 companies in `config/target_companies.yaml`. |
| **Wellfound (B)** | India startup volume | Public listing scrape via `httpx` + `selectolax`. |
| **X / Twitter (E)** | Founder "we're hiring" tweets | `snscrape` keyword queries. No paid API. |
| **Hacker News "Who is hiring" (G)** | Monthly remote/India leads | Algolia HN API; parse the pinned monthly thread. |
| **Gmail (F)** | Aggregator + signal channel | Gmail API (OAuth installed app flow). Parses (a) recruiter outreach, (b) LinkedIn/Wellfound job-alert digests. **Not a discovery scraper — it consolidates what already lands in the inbox.** |

**Explicitly excluded:**
- LinkedIn direct scraping (account-ban risk). Use LinkedIn's email alerts → Gmail parser instead.
- YC's "Work at a Startup" (gated; manual weekly sweep instead).
- Paid X API tier (overkill for the use case).

## 4. Architecture

```
              ┌──────────────────────────────────────┐
              │  cron (daily, 9:00 IST)              │
              │  scripts/run_scrapers.sh             │
              └──────────────┬───────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼─────┐        ┌─────▼────┐        ┌──────▼─────┐
   │ scrapers │        │ pipeline │        │  analyzer  │
   │ (per src)│───────▶│ normalize│───────▶│ (on demand │
   │          │        │ dedupe   │        │  + weekly) │
   │          │        │ enrich   │        │            │
   └──────────┘        └────┬─────┘        └──────┬─────┘
                            │                     │
                       ┌────▼─────────────────────▼────┐
                       │     data/jobs.db (SQLite)     │
                       └──────────────┬────────────────┘
                                      │
                              ┌───────▼────────┐
                              │  Streamlit     │
                              │  dashboard     │
                              └────────────────┘
```

**Component boundaries:**
- Each **scraper** outputs the same intermediate JSON shape (raw rows with `source`, `external_id`, `raw_payload`). Scrapers know nothing about the DB.
- **Pipeline** (`normalize → dedupe → enrich`) is the only writer to the `jobs` table. Scrapers write to a `staging` table; the pipeline promotes rows.
- **Dashboard** is read-mostly. The only writes from the dashboard are user actions (shortlist, mark applied, log a manual event) — these go through a thin `db.py` API, not raw SQL.
- **Analyzer** is read-only.

This separation means: adding a new source = writing one scraper file + an entry in `config/`. Nothing else changes.

## 5. Folder layout

```
job-hunt/
├── README.md
├── pyproject.toml              # uv-managed
├── .env.example
├── .gitignore
├── config/
│   ├── target_companies.yaml
│   ├── keywords.yaml
│   └── resume_variants.yaml
├── data/
│   ├── jobs.db
│   ├── resumes/
│   └── reports/                # weekly analyzer markdown reports
├── src/job_hunt/
│   ├── __init__.py
│   ├── db.py                   # SQLAlchemy models + thin query API
│   ├── scrapers/
│   │   ├── base.py             # Scraper protocol
│   │   ├── careers_pages.py
│   │   ├── wellfound.py
│   │   ├── x_search.py
│   │   ├── hn_hiring.py
│   │   └── gmail_inbox.py
│   ├── pipeline/
│   │   ├── normalize.py
│   │   ├── dedupe.py
│   │   └── enrich.py
│   ├── dashboard/
│   │   └── app.py
│   └── analyzer/
│       ├── metrics.py
│       ├── gap_finder.py
│       └── weekly_report.py
├── scripts/
│   ├── run_scrapers.sh
│   └── setup_gmail.py
└── tests/
    ├── test_pipeline.py
    ├── test_analyzer.py
    └── fixtures/
```

## 6. Data model (SQLite, via SQLAlchemy)

### `jobs`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `source` | TEXT NOT NULL | `careers`, `wellfound`, `x`, `hn`, `gmail` |
| `external_id` | TEXT | Stable per-source ID (URL hash if absent) |
| `company` | TEXT NOT NULL | Normalized casing |
| `title` | TEXT NOT NULL | |
| `url` | TEXT NOT NULL | Canonical |
| `jd_text` | TEXT | Full JD if scrapable; nullable for x/hn snippets |
| `location` | TEXT | |
| `posted_at` | DATETIME | |
| `scraped_at` | DATETIME NOT NULL | |
| `role_tag` | TEXT | `swe`, `ml`, `ai`, `frontend`, `backend`, `data`, `other` |
| `seniority_tag` | TEXT | `intern`, `new_grad`, `junior`, `mid`, `senior` |
| `tech_tags` | JSON | `["python","langchain","kubernetes",...]` |
| `status` | TEXT NOT NULL DEFAULT `'new'` | `new` `shortlisted` `applied` `replied` `rejected` `ghosted` `interviewing` `offer` `skipped` |
| `notes` | TEXT | User-editable from dashboard |

**Unique:** `(source, external_id)`.

### `applications`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `job_id` | INTEGER FK → jobs.id | |
| `applied_at` | DATETIME NOT NULL | |
| `resume_variant` | TEXT | e.g. `ai-ml`, `swe-startup` |
| `cover_note_path` | TEXT | Optional path to cover note used |
| `channel` | TEXT | `direct`, `referral`, `linkedin`, `email`, `x_dm` |

### `events`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `application_id` | INTEGER FK → applications.id | |
| `kind` | TEXT NOT NULL | `reply`, `rejection`, `recruiter_call`, `oa`, `interview`, `offer`, `withdrawn` |
| `happened_at` | DATETIME NOT NULL | |
| `source` | TEXT | `gmail`, `manual` |
| `raw_text` | TEXT | Original email body if from Gmail |

### `contacts`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `name` | TEXT | |
| `company` | TEXT | |
| `role` | TEXT | |
| `x_handle` | TEXT | |
| `linkedin_url` | TEXT | |
| `email` | TEXT | |
| `last_touched_at` | DATETIME | |
| `notes` | TEXT | |

### `gmail_messages`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `msg_id` | TEXT UNIQUE NOT NULL | Gmail message ID — idempotency key |
| `from_addr` | TEXT | |
| `subject` | TEXT | |
| `received_at` | DATETIME | |
| `job_id_match` | INTEGER FK → jobs.id NULL | Best-effort link to a job row |
| `parsed_signal` | TEXT | `recruiter_outreach`, `job_alert`, `interview_invite`, `rejection`, `noise` |

### `staging_raw`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `source` | TEXT NOT NULL | |
| `external_id` | TEXT NOT NULL | |
| `payload` | JSON NOT NULL | Whole scraper output blob |
| `scraped_at` | DATETIME NOT NULL | |
| `promoted` | BOOLEAN DEFAULT FALSE | Pipeline sets true after writing to `jobs` |

Staging exists so a misbehaving normalizer can be re-run without re-scraping.

## 7. Pipeline behavior

**`normalize.py`** — reads `staging_raw` rows with `promoted=false`, applies per-source mappers to produce `jobs`-table-shaped dicts. Pure functions, unit-tested with fixtures.

**`dedupe.py`** — for each candidate, computes (a) URL hash, (b) fuzzy match on `(company, title)` using `rapidfuzz.token_set_ratio >= 92`. If either matches an existing row, merge into that row (update `scraped_at`, preserve user-touched fields like `status`/`notes`).

**`enrich.py`** — assigns `role_tag`, `seniority_tag`, `tech_tags` by keyword rules in `config/keywords.yaml`. Initial version is purely rule-based — no LLM call in the hot path. (LLM enrichment is a future enhancement and explicitly out of scope for v1.)

## 8. Dashboard (Streamlit)

Four pages, navigation via sidebar.

### Page 1 — Inbox
- Default view: jobs with `status='new'` from the last 7 days.
- Filters: source, role_tag, seniority_tag, company (multi-select).
- Per row: company, title, location, posted_at, JD excerpt, link, action buttons → `Shortlist` / `Skip`.
- Bulk action: select N rows → Shortlist/Skip.

### Page 2 — Pipeline
- Kanban-style columns rendered with Streamlit columns: `shortlisted → applied → replied → interviewing → offer/rejected`. Drag-drop is not feasible in vanilla Streamlit, so status changes happen via a per-card dropdown — explicitly chosen over building a custom React component for v1.
- Clicking a card opens a side panel where the user can change status, log a new event, and edit notes inline.
- Setting status to `applied` prompts for `resume_variant` and `channel`; creates an `applications` row.

### Page 3 — Analytics
- Response rate by: company tier (small/mid/large by employee count), role_tag, resume_variant, channel, day-of-week applied.
- Time-to-first-response histogram.
- "Top dead-end patterns" (auto-surfaced from analyzer output).

### Page 4 — Today
- A single prioritized to-do list pulled from rules:
  - Shortlisted-but-not-applied jobs older than 3 days → "apply or skip".
  - Applications with no reply after 14 days → "follow up".
  - X contacts with `last_touched_at > 30 days ago` → "re-engage".
  - This week's analyzer recommendations.

## 9. Analyzer

**`metrics.py`** — pure SQL aggregation functions. Each returns a tidy DataFrame consumed by both the dashboard and the weekly report.

**`gap_finder.py`** — for each ghosted/rejected application:
1. Tokenize the JD; remove stopwords + boilerplate.
2. Tokenize the resume variant used.
3. Compute set-difference (JD-only tokens) weighted by frequency across multiple ghosted JDs.
4. Surface the top-N tokens that appear in many ghosted JDs but rarely/never in the user's resume.

This is intentionally simple (TF-IDF, no embeddings) for v1. It's good enough to catch "12 JDs want 'distributed systems' — your resume mentions it 0 times" and ships in <100 LOC.

**`weekly_report.py`** — runs every Sunday via cron. Writes `data/reports/YYYY-WW.md` with:
1. Week's activity (new jobs, applied, replied, rejected counts).
2. Response-rate breakdowns from `metrics.py`.
3. Top 10 gap tokens from `gap_finder.py`.
4. Three explicit "actions for next week" (rule-based: e.g., if response rate at >5000-employee cos is 0% with ≥10 apps, recommend reallocating to <500-employee).

## 10. Gmail integration

- One-time setup: `python scripts/setup_gmail.py` runs the OAuth installed-app flow, writes a refresh token to `data/.gmail_token.json` (in `.gitignore`).
- Scraper fetches messages since `MAX(received_at)` in `gmail_messages`. New messages only.
- Parsing strategy (rule-based, v1):
  - Sender domain + subject keywords → classify into `parsed_signal` buckets.
  - Recruiter outreach + job mention → create a `jobs` row (source=`gmail`).
  - Reply/rejection patterns on threads matching an existing application → create an `events` row.
- Idempotent: replay-safe via `msg_id` unique constraint.

## 11. X (snscrape)

- Configurable query list in `config/keywords.yaml`, e.g. `"hiring" lang:en since:2026-05-19 (ML OR "machine learning" OR LLM) (India OR remote)`.
- Pulls tweets, filters for ones containing an Apply link or recruiter handle, writes to `staging_raw`.
- One row per tweet; dedupe handles re-tweets across queries.
- Snscrape lib is unmaintained but currently functional. If it breaks, fallback is the Nitter-instance HTTP scrape — covered in implementation plan as a risk item, not blocking for v1.

## 12. Scheduling

Two cron entries:

```cron
# Daily scrape + pipeline, 09:00 IST
0 9 * * *   cd ~/creative-task/job-hunt && scripts/run_scrapers.sh >> data/cron.log 2>&1

# Weekly analyzer report, Sunday 18:00 IST
0 18 * * 0  cd ~/creative-task/job-hunt && uv run python -m job_hunt.analyzer.weekly_report >> data/cron.log 2>&1
```

`run_scrapers.sh` runs scrapers in parallel where safe (Wellfound, HN, X are independent), then runs the pipeline (`normalize → dedupe → enrich`) serially. Gmail scraper runs serially after the parallel block so the pipeline sees all sources at once.

## 13. Testing

- **Unit:** `normalize` mappers (per-source), `dedupe` (fuzzy match cases), `enrich` (tag rules), `gap_finder` (TF-IDF math). Fixtures live in `tests/fixtures/`.
- **Integration:** end-to-end with a seeded in-memory SQLite DB feeding the dashboard's underlying queries.
- **No E2E dashboard tests** in v1 (Streamlit testing is heavy; manual verification is fine for single-user tooling).

## 14. Security & secrets

- `.env` for any secrets; `.gitignore`'d.
- Gmail OAuth token stored at `data/.gmail_token.json`, also gitignored.
- All scraping respects per-site `robots.txt` and uses conservative rate limits (≥3s between requests by default).
- No PII beyond Saksham's own contacts table.

## 15. Out of scope (explicit)

- LLM-based JD enrichment (rule-based v1; LLM is a follow-up).
- Embedding-based resume↔JD matching (TF-IDF v1; embeddings are a follow-up).
- Auto-apply / auto-DM (intentional decision; never).
- Cloud deployment / hosted dashboard.
- Multi-user support / auth.
- Mobile UI.
- Browser extension for one-click "save this JD".

## 16. Open risks / decisions made anyway

| Risk | Mitigation |
|---|---|
| `snscrape` breaks (X changes anti-bot) | Fallback to Nitter HTTP scrape; if both fail, X source is paused and surfaced in the weekly report. |
| Gmail OAuth quota | Free tier is more than enough for a single user; revisit only if exceeded. |
| Careers-page adapters drift | Each adapter is small and isolated; treat breakage as expected and budget ~30 min/month for maintenance. |
| SQLite concurrency (cron writer + dashboard reader) | WAL mode enabled; reads are non-blocking. |
| User abandons the system after week 1 | The "Today" page exists precisely to lower the daily-friction cost. Weekly report is a forcing function. |

## 17. Success criteria

After 4 weeks of operation:
- ≥80% of all applied jobs originate from the dashboard (not random browsing).
- The weekly report has surfaced at least one actionable resume gap that the user has acted on.
- Response rate is **measurable** — that's the win even if the absolute number is low. The system is what makes it measurable, and measurement is what enables iteration.
