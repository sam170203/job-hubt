from datetime import datetime

from job_hunt.pipeline.normalize import (
    NormalizedJob,
    normalize_gmail_payload,
    normalize_greenhouse_payload,
    normalize_hn_payload,
    normalize_lever_payload,
    normalize_wellfound_payload,
    normalize_x_payload,
)


def test_normalize_clean_pipe_format():
    payload = {
        "text": "<p>Acme Corp | ML Engineer | Remote (India) | $80k-120k | "
        'Apply: <a href="https://acme.io/jobs">acme.io/jobs</a></p>',
        "author": "acme_founder",
        "created_at": "2026-05-25T10:00:00Z",
    }
    norm = normalize_hn_payload(
        external_id="123", payload=payload, scraped_at=datetime(2026, 5, 26)
    )
    assert isinstance(norm, NormalizedJob)
    assert norm.company == "Acme Corp"
    assert norm.title == "ML Engineer"
    assert norm.location == "Remote (India)"
    assert norm.url == "https://acme.io/jobs"
    assert norm.source == "hn"
    assert norm.external_id == "123"


def test_normalize_no_pipes_falls_back():
    payload = {"text": "We are hiring engineers, DM me", "author": "x"}
    norm = normalize_hn_payload(external_id="9", payload=payload, scraped_at=datetime(2026, 5, 26))
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


# ---------------------------------------------------------------------------
# Greenhouse
# ---------------------------------------------------------------------------


def test_normalize_greenhouse_full():
    payload = {
        "company": "DeepMind",
        "job": {
            "id": "gh123",
            "title": "Research Scientist",
            "absolute_url": "https://deepmind.com/jobs/gh123",
            "location": {"name": "London, UK"},
            "updated_at": "2026-05-20T12:00:00Z",
            "content": "<p>Work on AGI research.</p>",
        },
    }
    norm = normalize_greenhouse_payload("gh123", payload, scraped_at=datetime(2026, 5, 26))
    assert isinstance(norm, NormalizedJob)
    assert norm.source == "greenhouse"
    assert norm.external_id == "gh123"
    assert norm.company == "DeepMind"
    assert norm.title == "Research Scientist"
    assert norm.url == "https://deepmind.com/jobs/gh123"
    assert norm.location == "London, UK"
    assert norm.jd_text == "Work on AGI research."
    assert norm.posted_at is not None


def test_normalize_greenhouse_missing_fields():
    payload = {
        "company": "Startup",
        "job": {"id": "gh99", "title": "Engineer", "absolute_url": "https://co.com/j/99"},
    }
    norm = normalize_greenhouse_payload("gh99", payload, scraped_at=datetime(2026, 5, 26))
    assert norm.company == "Startup"
    assert norm.title == "Engineer"
    assert norm.location is None
    assert norm.jd_text is None
    assert norm.posted_at is None


# ---------------------------------------------------------------------------
# Lever
# ---------------------------------------------------------------------------


def test_normalize_lever_full():
    payload = {
        "company": "Stripe",
        "posting": {
            "id": "lv1",
            "text": "Backend Engineer",
            "hostedUrl": "https://jobs.lever.co/stripe/lv1",
            "categories": {"location": "San Francisco"},
            "descriptionPlain": "Build payment systems.",
            "createdAt": 1716393600000,  # some epoch ms
        },
    }
    norm = normalize_lever_payload("lv1", payload, scraped_at=datetime(2026, 5, 26))
    assert isinstance(norm, NormalizedJob)
    assert norm.source == "lever"
    assert norm.company == "Stripe"
    assert norm.title == "Backend Engineer"
    assert norm.url == "https://jobs.lever.co/stripe/lv1"
    assert norm.location == "San Francisco"
    assert norm.jd_text == "Build payment systems."
    assert norm.posted_at is not None


def test_normalize_lever_html_description_fallback():
    payload = {
        "company": "Acme",
        "posting": {
            "id": "lv2",
            "text": "DevOps Lead",
            "hostedUrl": "https://jobs.lever.co/acme/lv2",
            "description": "<p>Manage infra and CI pipelines.</p>",
        },
    }
    norm = normalize_lever_payload("lv2", payload, scraped_at=datetime(2026, 5, 26))
    assert norm.jd_text == "Manage infra and CI pipelines."
    assert norm.location is None
    assert norm.posted_at is None


# ---------------------------------------------------------------------------
# Wellfound
# ---------------------------------------------------------------------------


def test_normalize_wellfound_full():
    payload = {
        "url": "https://wellfound.com/jobs/wf1",
        "job_ld": {
            "@type": "JobPosting",
            "title": "ML Engineer",
            "hiringOrganization": {"name": "CoolStartup"},
            "description": "<p>Train and deploy models.</p>",
            "jobLocation": {
                "address": {
                    "addressLocality": "Bangalore",
                    "addressRegion": "Karnataka",
                    "addressCountry": "India",
                }
            },
            "datePosted": "2026-05-15",
        },
    }
    norm = normalize_wellfound_payload("wf1", payload, scraped_at=datetime(2026, 5, 26))
    assert isinstance(norm, NormalizedJob)
    assert norm.source == "wellfound"
    assert norm.company == "CoolStartup"
    assert norm.title == "ML Engineer"
    assert norm.url == "https://wellfound.com/jobs/wf1"
    assert norm.jd_text == "Train and deploy models."
    assert "Bangalore" in (norm.location or "")
    assert norm.posted_at is not None


def test_normalize_wellfound_missing_fields():
    payload = {
        "url": "https://wellfound.com/jobs/wf2",
        "job_ld": {"title": "Product Manager"},
    }
    norm = normalize_wellfound_payload("wf2", payload, scraped_at=datetime(2026, 5, 26))
    assert norm.company == "Unknown"
    assert norm.title == "Product Manager"
    assert norm.location is None
    assert norm.jd_text is None
    assert norm.posted_at is None


# ---------------------------------------------------------------------------
# X (Twitter)
# ---------------------------------------------------------------------------


def test_normalize_x_full():
    payload = {
        "id": "tweet1",
        "url": "https://twitter.com/founder1/status/tweet1",
        "text": "We are hiring ML engineers in India! DM us or apply at https://co.io/jobs",
        "author": "@founder1",
        "date": "2026-05-24T08:00:00Z",
        "query": "hiring ML India",
    }
    norm = normalize_x_payload("tweet1", payload, scraped_at=datetime(2026, 5, 26))
    assert isinstance(norm, NormalizedJob)
    assert norm.source == "x"
    assert norm.company == "@founder1"
    assert norm.title == payload["text"][:120]
    assert norm.url == "https://twitter.com/founder1/status/tweet1"
    assert norm.jd_text == payload["text"]
    assert norm.location is None
    assert norm.posted_at is not None


def test_normalize_x_missing_date():
    payload = {
        "id": "tweet2",
        "url": "https://twitter.com/u/status/tweet2",
        "text": "Hiring!",
        "author": "@someone",
        "date": None,
        "query": "",
    }
    norm = normalize_x_payload("tweet2", payload, scraped_at=datetime(2026, 5, 26))
    assert norm.company == "@someone"
    assert norm.posted_at is None
    assert norm.jd_text == "Hiring!"


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------


def test_normalize_gmail_full():
    payload = {
        "msg_id": "gm1",
        "from_addr": "recruiter@acme.com",
        "subject": "ML Engineer role at Acme",
        "received_at": "2026-05-26T10:00:00",
        "body_excerpt": "We have an exciting ML role open.",
        "signal": "recruiter_outreach",
    }
    norm = normalize_gmail_payload("gm1", payload, scraped_at=datetime(2026, 5, 26))
    assert isinstance(norm, NormalizedJob)
    assert norm.source == "gmail"
    assert norm.company == "acme"
    assert norm.title == "ML Engineer role at Acme"
    assert "gm1" in norm.url
    assert norm.jd_text == "We have an exciting ML role open."
    assert norm.location is None
    assert norm.posted_at is not None


def test_normalize_gmail_missing_fields():
    payload = {
        "msg_id": "gm2",
        "from_addr": "",
        "subject": "",
        "received_at": None,
        "body_excerpt": None,
        "signal": "",
    }
    norm = normalize_gmail_payload("gm2", payload, scraped_at=datetime(2026, 5, 26))
    assert norm.company == "Unknown"
    assert norm.title == ""
    assert norm.jd_text is None
    assert norm.posted_at is None
    assert "gm2" in norm.url
