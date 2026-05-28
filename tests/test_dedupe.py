from datetime import datetime

from job_hunt import db
from job_hunt.models import Job
from job_hunt.pipeline.dedupe import DedupeResult, find_duplicate
from job_hunt.pipeline.normalize import NormalizedJob


def _norm(company="Acme", title="ML Engineer", url="https://acme.io/jobs", ext_id="x"):
    return NormalizedJob(
        source="hn", external_id=ext_id, company=company, title=title, url=url,
        jd_text=None, location=None, posted_at=None,
        scraped_at=datetime(2026, 5, 26),
    )


def _seed(session, **kw):
    j = Job(
        source=kw.get("source", "hn"),
        external_id=kw.get("external_id", "seed-x"),
        company=kw["company"],
        title=kw["title"],
        url=kw["url"],
        scraped_at=datetime(2026, 5, 25),
    )
    session.add(j)
    session.flush()
    return j


def test_no_duplicate_on_empty_db(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        result = find_duplicate(s, _norm())
    assert result == DedupeResult.new()


def test_url_exact_match_is_duplicate(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        existing = _seed(s, company="Acme", title="X", url="https://acme.io/jobs")
        existing_id = existing.id
        result = find_duplicate(s, _norm(url="https://acme.io/jobs"))
    assert result.is_duplicate
    assert result.existing_id == existing_id


def test_fuzzy_company_title_match_is_duplicate(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        existing = _seed(s, company="Google Cloud",
                         title="Backend Engineer", url="https://other.url")
        existing_id = existing.id
        result = find_duplicate(s, _norm(company="Google Cloud",
                                         title="Backend Software Engineer",
                                         url="https://different.url"))
    assert result.is_duplicate
    assert result.existing_id == existing_id


def test_different_company_is_new(tmp_data_dir):
    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        _seed(s, company="Acme", title="ML", url="https://a.com")
        result = find_duplicate(s, _norm(company="Zenith Labs",
                                         title="Backend Engineer",
                                         url="https://z.com"))
    assert not result.is_duplicate
