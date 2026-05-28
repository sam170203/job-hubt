"""Tiny additive-only migrations runner.

Each migration is a (version, description, callable) tuple. The callable receives
an open SQLAlchemy Connection. Migrations are applied in version order; already-applied
ones are skipped (tracked in the schema_migrations table).

Constraints:
- Additive only — no DROP/RENAME without a follow-up migration.
- Idempotent at the runner level — re-running init_db is safe.
- No down-migrations in v1.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

Migration = tuple[int, str, Callable[[Connection], None]]


def _ensure_schema_migrations(conn: Connection) -> None:
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  version INTEGER PRIMARY KEY,"
            "  applied_at DATETIME NOT NULL"
            ")"
        )
    )


def _applied(conn: Connection) -> set[int]:
    return {row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))}


def _column_exists(conn: Connection, table: str, col: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).all()
    return any(r[1] == col for r in rows)


def _add_col_if_missing(conn: Connection, table: str, col: str, sql_type: str) -> None:
    if not _column_exists(conn, table, col):
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {sql_type}"))


def _table_exists(conn: Connection, table: str) -> bool:
    insp = inspect(conn)
    return table in insp.get_table_names()


# --- Migrations ---


def m1_add_jobs_columns(conn: Connection) -> None:
    _add_col_if_missing(conn, "jobs", "work_mode", "TEXT")
    _add_col_if_missing(conn, "jobs", "country", "TEXT")
    _add_col_if_missing(conn, "jobs", "india_state", "TEXT")
    _add_col_if_missing(conn, "jobs", "company_tier", "TEXT")
    _add_col_if_missing(conn, "jobs", "match_score", "REAL")
    _add_col_if_missing(conn, "jobs", "hidden", "BOOLEAN DEFAULT 0 NOT NULL")


def m2_create_aux_tables(conn: Connection) -> None:
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS company_blocklist ("
            "  id INTEGER PRIMARY KEY,"
            "  company_name TEXT UNIQUE NOT NULL,"
            "  reason TEXT,"
            "  created_at DATETIME NOT NULL"
            ")"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS saved_views ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT UNIQUE NOT NULL,"
            "  filters_json TEXT NOT NULL,"
            "  created_at DATETIME NOT NULL"
            ")"
        )
    )


MIGRATIONS: list[Migration] = [
    (
        1,
        "add jobs columns: work_mode, country, india_state, company_tier, match_score, hidden",
        m1_add_jobs_columns,
    ),
    (2, "create company_blocklist + saved_views tables", m2_create_aux_tables),
]


def run_migrations(engine: Engine) -> None:
    with engine.begin() as conn:
        _ensure_schema_migrations(conn)
        applied = _applied(conn)
        for version, _desc, fn in MIGRATIONS:
            if version in applied:
                continue
            fn(conn)
            conn.execute(
                text("INSERT INTO schema_migrations (version, applied_at) VALUES (:v, :t)"),
                {"v": version, "t": datetime.utcnow()},
            )
