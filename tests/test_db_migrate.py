from sqlalchemy import inspect, text

from job_hunt import db
from job_hunt.db_migrate import MIGRATIONS, run_migrations


def test_migrations_create_new_columns(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    eng = db.get_engine()
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("jobs")}
    assert {"work_mode", "country", "india_state", "company_tier",
            "match_score", "hidden"} <= cols


def test_migrations_create_new_tables(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    eng = db.get_engine()
    insp = inspect(eng)
    tables = set(insp.get_table_names())
    assert {"company_blocklist", "saved_views", "schema_migrations"} <= tables


def test_migrations_idempotent(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    # Second init_db should be a no-op
    db.init_db()
    eng = db.get_engine()
    with eng.connect() as c:
        applied = c.execute(text("SELECT COUNT(*) FROM schema_migrations")).scalar()
    assert applied == len(MIGRATIONS)
