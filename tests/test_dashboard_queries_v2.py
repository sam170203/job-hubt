from datetime import datetime, timedelta

from job_hunt import db
from job_hunt.dashboard.queries import (
    apply_to_job,
    blocklist_company,
    get_inbox_jobs,
    list_applied_jobs,
    list_saved_views,
    save_view,
)
from job_hunt.models import Application, CompanyBlocklist, Job


def _seed(s, **kw):
    defaults = dict(
        source="hn", company="A", title="T", url="u", scraped_at=datetime.utcnow(), status="new"
    )
    defaults.update(kw)
    j = Job(**defaults)
    s.add(j)
    s.flush()
    return j


def test_inbox_filter_work_mode(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, external_id="1", url="u1", work_mode="remote")
        _seed(s, external_id="2", url="u2", work_mode="onsite")
    rows = get_inbox_jobs(work_modes=["remote"])
    assert len(rows) == 1


def test_inbox_filter_country(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, external_id="1", url="u1", country="India")
        _seed(s, external_id="2", url="u2", country="USA")
    rows = get_inbox_jobs(countries=["India"])
    assert len(rows) == 1


def test_inbox_filter_india_state(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, external_id="1", url="u1", country="India", india_state="Karnataka")
        _seed(s, external_id="2", url="u2", country="India", india_state="Delhi")
    rows = get_inbox_jobs(india_states=["Karnataka"])
    assert len(rows) == 1


def test_inbox_filter_company_tier(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, external_id="1", url="u1", company_tier="startup")
        _seed(s, external_id="2", url="u2", company_tier="mnc")
    rows = get_inbox_jobs(company_tiers=["startup"])
    assert len(rows) == 1


def test_inbox_filter_min_match_score(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, external_id="1", url="u1", match_score=0.8)
        _seed(s, external_id="2", url="u2", match_score=0.2)
    rows = get_inbox_jobs(min_match_score=0.5)
    assert len(rows) == 1


def test_inbox_filter_skills_intersect(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, external_id="1", url="u1", tech_tags=["python", "pytorch"])
        _seed(s, external_id="2", url="u2", tech_tags=["react"])
    rows = get_inbox_jobs(required_skills=["python"])
    assert len(rows) == 1


def test_inbox_excludes_hidden(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, external_id="1", url="u1", hidden=True)
        _seed(s, external_id="2", url="u2", hidden=False)
    rows = get_inbox_jobs()
    assert len(rows) == 1
    assert rows[0].external_id == "2"


def test_inbox_default_sort_match_then_date(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    now = datetime.utcnow()
    with db.session_scope() as s:
        _seed(s, external_id="1", url="u1", match_score=0.2, scraped_at=now)
        _seed(s, external_id="2", url="u2", match_score=0.9, scraped_at=now - timedelta(hours=1))
    rows = get_inbox_jobs()
    assert rows[0].external_id == "2"


def test_apply_to_job_creates_application(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        j = _seed(s, external_id="1", url="u1")
        jid = j.id

    apply_to_job(jid, resume_variant="ai-ml", channel="direct", note="ref Saksham")

    with db.session_scope() as s:
        assert s.get(Job, jid).status == "applied"
        apps = s.query(Application).all()
        assert len(apps) == 1
        assert apps[0].resume_variant == "ai-ml"
        assert apps[0].channel == "direct"


def test_blocklist_company_hides_all_rows(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, external_id="1", url="u1", company="Acme")
        _seed(s, external_id="2", url="u2", company="Acme")
        _seed(s, external_id="3", url="u3", company="Other")

    blocklist_company("Acme", reason="not aligned")

    with db.session_scope() as s:
        acme_rows = s.query(Job).filter(Job.company == "Acme").all()
        assert all(r.hidden for r in acme_rows)
        assert s.query(CompanyBlocklist).count() == 1


def test_list_applied_returns_joined(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        j = _seed(s, external_id="1", url="u1", company="Acme", title="ML Eng")
        jid = j.id
    apply_to_job(jid, resume_variant="ai-ml", channel="direct")

    rows = list_applied_jobs()
    assert len(rows) == 1
    assert rows[0].company == "Acme"
    assert rows[0].title == "ML Eng"


def test_saved_views_roundtrip(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    save_view(
        "ML India Remote",
        {"role_tags": ["ml"], "countries": ["India"], "work_modes": ["remote"]},
    )
    views = list_saved_views()
    assert any(v.name == "ML India Remote" for v in views)
