"""Tests for the careers_pages scraper (Greenhouse + Lever ATS adapters)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from job_hunt.scrapers.base import RawJob
from job_hunt.scrapers.careers_pages import (
    CareersPagesScraper,
    fetch_greenhouse,
    fetch_lever,
    gh_job_to_raw,
    lever_posting_to_raw,
)

# ---------------------------------------------------------------------------
# Unit tests for conversion helpers
# ---------------------------------------------------------------------------


def test_gh_job_to_raw_produces_correct_source():
    job = {"id": 12345, "title": "ML Engineer"}
    raw = gh_job_to_raw("Acme", job)
    assert raw.source == "greenhouse"


def test_gh_job_to_raw_external_id():
    job = {"id": 12345, "title": "ML Engineer"}
    raw = gh_job_to_raw("Acme", job)
    assert raw.external_id == "Acme:12345"


def test_gh_job_to_raw_payload_contains_company_and_job():
    job = {"id": 99, "title": "SWE"}
    raw = gh_job_to_raw("TestCo", job)
    assert raw.payload["company"] == "TestCo"
    assert raw.payload["job"] == job


def test_gh_job_to_raw_falls_back_to_internal_job_id():
    job = {"internal_job_id": 777, "title": "PM"}
    raw = gh_job_to_raw("Acme", job)
    assert raw.external_id == "Acme:777"


def test_gh_job_to_raw_returns_rawtjob_instance():
    job = {"id": 1}
    assert isinstance(gh_job_to_raw("X", job), RawJob)


def test_lever_posting_to_raw_produces_correct_source():
    posting = {"id": "abc-123", "text": "Backend Engineer"}
    raw = lever_posting_to_raw("Startupco", posting)
    assert raw.source == "lever"


def test_lever_posting_to_raw_external_id():
    posting = {"id": "abc-123", "text": "Backend Engineer"}
    raw = lever_posting_to_raw("Startupco", posting)
    assert raw.external_id == "Startupco:abc-123"


def test_lever_posting_to_raw_payload_contains_company_and_posting():
    posting = {"id": "x1", "text": "Designer"}
    raw = lever_posting_to_raw("DesignCo", posting)
    assert raw.payload["company"] == "DesignCo"
    assert raw.payload["posting"] == posting


def test_lever_posting_to_raw_returns_rawjob_instance():
    posting = {"id": "z9"}
    assert isinstance(lever_posting_to_raw("Y", posting), RawJob)


# ---------------------------------------------------------------------------
# fetch_greenhouse — error handling
# ---------------------------------------------------------------------------


def test_fetch_greenhouse_returns_list_on_success():
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"jobs": [{"id": 1}, {"id": 2}]}
    fake_resp.raise_for_status.return_value = None

    with patch("job_hunt.scrapers.careers_pages.httpx.get", return_value=fake_resp):
        result = fetch_greenhouse("testslug")

    assert result == [{"id": 1}, {"id": 2}]


def test_fetch_greenhouse_returns_empty_list_on_http_error():
    fake_resp = MagicMock()
    fake_resp.raise_for_status.side_effect = Exception("404 Not Found")

    with patch("job_hunt.scrapers.careers_pages.httpx.get", return_value=fake_resp):
        result = fetch_greenhouse("nonexistent-slug")

    assert result == []


def test_fetch_greenhouse_returns_empty_list_on_connection_error():
    with patch(
        "job_hunt.scrapers.careers_pages.httpx.get",
        side_effect=Exception("Connection refused"),
    ):
        result = fetch_greenhouse("any-slug")

    assert result == []


def test_fetch_greenhouse_handles_missing_jobs_key():
    fake_resp = MagicMock()
    fake_resp.json.return_value = {}
    fake_resp.raise_for_status.return_value = None

    with patch("job_hunt.scrapers.careers_pages.httpx.get", return_value=fake_resp):
        result = fetch_greenhouse("slug-no-jobs-key")

    assert result == []


# ---------------------------------------------------------------------------
# fetch_lever — error handling
# ---------------------------------------------------------------------------


def test_fetch_lever_returns_list_on_success():
    fake_resp = MagicMock()
    fake_resp.json.return_value = [{"id": "p1"}, {"id": "p2"}]
    fake_resp.raise_for_status.return_value = None

    with patch("job_hunt.scrapers.careers_pages.httpx.get", return_value=fake_resp):
        result = fetch_lever("testslug")

    assert result == [{"id": "p1"}, {"id": "p2"}]


def test_fetch_lever_returns_empty_list_on_http_error():
    fake_resp = MagicMock()
    fake_resp.raise_for_status.side_effect = Exception("403 Forbidden")

    with patch("job_hunt.scrapers.careers_pages.httpx.get", return_value=fake_resp):
        result = fetch_lever("bad-slug")

    assert result == []


def test_fetch_lever_returns_empty_list_on_connection_error():
    with patch(
        "job_hunt.scrapers.careers_pages.httpx.get",
        side_effect=Exception("Timeout"),
    ):
        result = fetch_lever("any-slug")

    assert result == []


def test_fetch_lever_returns_empty_list_when_response_is_not_list():
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"error": "not found"}
    fake_resp.raise_for_status.return_value = None

    with patch("job_hunt.scrapers.careers_pages.httpx.get", return_value=fake_resp):
        result = fetch_lever("bad-response-slug")

    assert result == []


# ---------------------------------------------------------------------------
# CareersPagesScraper.run() — integration-style (all mocked)
# ---------------------------------------------------------------------------

_FAKE_COMPANIES = [
    {"name": "GHCo", "ats": "greenhouse", "slug": "ghco"},
    {"name": "LeverCo", "ats": "lever", "slug": "leverco"},
    {"name": "BadATS", "ats": "unknown", "slug": "whatever"},
    {"name": "", "ats": "greenhouse", "slug": "empty"},  # missing name — skipped
]

_FAKE_GH_JOBS = [{"id": 1}, {"id": 2}]
_FAKE_LEVER_POSTINGS = [{"id": "lv-1"}, {"id": "lv-2"}, {"id": "lv-3"}]


def _make_fake_httpx(gh_jobs, lever_postings):
    """Return a fake httpx.get that serves different payloads for GH vs Lever URLs."""

    def fake_get(url, timeout=None, **kwargs):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        if "greenhouse" in url:
            resp.json.return_value = {"jobs": gh_jobs}
        elif "lever" in url:
            resp.json.return_value = lever_postings
        else:
            resp.raise_for_status.side_effect = Exception("unknown url")
        return resp

    return fake_get


def test_careers_scraper_run_returns_correct_count():
    with (
        patch(
            "job_hunt.scrapers.careers_pages._load_target_companies",
            return_value=_FAKE_COMPANIES,
        ),
        patch(
            "job_hunt.scrapers.careers_pages.httpx.get",
            side_effect=_make_fake_httpx(_FAKE_GH_JOBS, _FAKE_LEVER_POSTINGS),
        ),
        patch("job_hunt.scrapers.careers_pages.time.sleep"),  # skip actual sleep
    ):
        rows = CareersPagesScraper().run()

    # GHCo → 2 greenhouse rows, LeverCo → 3 lever rows; BadATS + empty → 0
    assert len(rows) == 5


def test_careers_scraper_run_sources_are_correct():
    with (
        patch(
            "job_hunt.scrapers.careers_pages._load_target_companies",
            return_value=_FAKE_COMPANIES,
        ),
        patch(
            "job_hunt.scrapers.careers_pages.httpx.get",
            side_effect=_make_fake_httpx(_FAKE_GH_JOBS, _FAKE_LEVER_POSTINGS),
        ),
        patch("job_hunt.scrapers.careers_pages.time.sleep"),
    ):
        rows = CareersPagesScraper().run()

    sources = {r.source for r in rows}
    assert sources == {"greenhouse", "lever"}


def test_careers_scraper_run_external_ids():
    with (
        patch(
            "job_hunt.scrapers.careers_pages._load_target_companies",
            return_value=_FAKE_COMPANIES,
        ),
        patch(
            "job_hunt.scrapers.careers_pages.httpx.get",
            side_effect=_make_fake_httpx(_FAKE_GH_JOBS, _FAKE_LEVER_POSTINGS),
        ),
        patch("job_hunt.scrapers.careers_pages.time.sleep"),
    ):
        rows = CareersPagesScraper().run()

    ids = {r.external_id for r in rows}
    assert "GHCo:1" in ids
    assert "GHCo:2" in ids
    assert "LeverCo:lv-1" in ids
    assert "LeverCo:lv-2" in ids
    assert "LeverCo:lv-3" in ids


def test_careers_scraper_run_skips_entry_with_missing_name():
    """The entry with name='' should be silently skipped."""
    companies_with_missing_name = [{"name": "", "ats": "greenhouse", "slug": "x"}]

    with (
        patch(
            "job_hunt.scrapers.careers_pages._load_target_companies",
            return_value=companies_with_missing_name,
        ),
        patch(
            "job_hunt.scrapers.careers_pages.httpx.get",
            side_effect=_make_fake_httpx(_FAKE_GH_JOBS, _FAKE_LEVER_POSTINGS),
        ),
        patch("job_hunt.scrapers.careers_pages.time.sleep"),
    ):
        rows = CareersPagesScraper().run()

    assert rows == []


def test_careers_scraper_run_handles_all_404s_gracefully():
    """If every company 404s, run() returns [] without raising."""

    def always_error(url, timeout=None, **kwargs):
        resp = MagicMock()
        resp.raise_for_status.side_effect = Exception("404")
        return resp

    with (
        patch(
            "job_hunt.scrapers.careers_pages._load_target_companies",
            return_value=_FAKE_COMPANIES,
        ),
        patch("job_hunt.scrapers.careers_pages.httpx.get", side_effect=always_error),
        patch("job_hunt.scrapers.careers_pages.time.sleep"),
    ):
        rows = CareersPagesScraper().run()

    assert rows == []


def test_careers_scraper_source_attribute():
    assert CareersPagesScraper.source == "careers"
