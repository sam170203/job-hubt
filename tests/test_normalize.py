from datetime import datetime

from job_hunt.pipeline.normalize import NormalizedJob, normalize_hn_payload


def test_normalize_clean_pipe_format():
    payload = {
        "text": "<p>Acme Corp | ML Engineer | Remote (India) | $80k-120k | "
                "Apply: <a href=\"https://acme.io/jobs\">acme.io/jobs</a></p>",
        "author": "acme_founder",
        "created_at": "2026-05-25T10:00:00Z",
    }
    norm = normalize_hn_payload(external_id="123", payload=payload,
                                scraped_at=datetime(2026, 5, 26))
    assert isinstance(norm, NormalizedJob)
    assert norm.company == "Acme Corp"
    assert norm.title == "ML Engineer"
    assert norm.location == "Remote (India)"
    assert norm.url == "https://acme.io/jobs"
    assert norm.source == "hn"
    assert norm.external_id == "123"


def test_normalize_no_pipes_falls_back():
    payload = {"text": "We are hiring engineers, DM me", "author": "x"}
    norm = normalize_hn_payload(external_id="9", payload=payload,
                                scraped_at=datetime(2026, 5, 26))
    assert norm.company == "Unknown (HN comment 9)"
    assert norm.title == "We are hiring engineers, DM me"[:120]
    assert norm.url.startswith("https://news.ycombinator.com/item?id=")


def test_normalize_strips_html():
    payload = {"text": "<p>A | B | C | <a href='https://x.io'>x.io</a></p>"}
    norm = normalize_hn_payload("1", payload, scraped_at=datetime(2026, 5, 26))
    assert "<" not in norm.company
    assert "<" not in norm.title


def test_normalize_picks_first_external_url_not_hn():
    payload = {
        "text": "Co | Role | Loc | "
                "<a href='https://news.ycombinator.com/user?id=x'>profile</a> "
                "<a href='https://co.com/jobs'>apply</a>"
    }
    norm = normalize_hn_payload("1", payload, scraped_at=datetime(2026, 5, 26))
    assert norm.url == "https://co.com/jobs"
