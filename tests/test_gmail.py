import base64
from unittest.mock import MagicMock, patch

from job_hunt.scrapers.gmail_inbox import (
    GmailInboxScraper,
    classify,
    extract_plain_text,
    message_to_raw,
)


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def test_classify_recruiter():
    assert classify("recruiter@acme.com", "Quick chat?", "We have a role for you.") \
        == "recruiter_outreach"


def test_classify_job_alert_by_domain():
    assert classify("noreply@linkedin.com", "Jobs you might like", "...") == "job_alert"


def test_classify_interview():
    assert classify("a@b.com", "Interview with Acme", "Let's schedule") == "interview_invite"


def test_classify_rejection():
    assert classify("a@b.com", "Application update",
                    "Unfortunately we will not be moving forward.") == "rejection"


def test_classify_noise():
    assert classify("friend@gmail.com", "lunch?", "hey") == "noise"


def test_extract_plain_text_simple():
    payload = {"mimeType": "text/plain", "body": {"data": _b64("hello world")}}
    assert extract_plain_text(payload) == "hello world"


def test_extract_plain_text_multipart_prefers_plain():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/html", "body": {"data": _b64("<p>HTML</p>")}},
            {"mimeType": "text/plain", "body": {"data": _b64("plain text version")}},
        ],
    }
    assert extract_plain_text(payload) == "plain text version"


def test_extract_plain_text_html_fallback():
    payload = {"mimeType": "text/html", "body": {"data": _b64("<p>Hello <b>X</b></p>")}}
    text = extract_plain_text(payload)
    assert "Hello" in text and "<" not in text


def test_message_to_raw_recruiter_emits_rawjob():
    msg = {
        "id": "abc123",
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": _b64("We have a role for you.")},
            "headers": [
                {"name": "From", "value": "recruiter@acme.com"},
                {"name": "Subject", "value": "Opportunity"},
                {"name": "Date", "value": "Mon, 26 May 2026 10:00:00 +0000"},
            ],
        },
    }
    signal, raw = message_to_raw(msg)
    assert signal == "recruiter_outreach"
    assert raw is not None
    assert raw.source == "gmail"
    assert raw.external_id == "abc123"


def test_message_to_raw_noise_returns_none():
    msg = {
        "id": "n1",
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": _b64("hey")},
            "headers": [
                {"name": "From", "value": "friend@gmail.com"},
                {"name": "Subject", "value": "lunch?"},
            ],
        },
    }
    signal, raw = message_to_raw(msg)
    assert signal == "noise"
    assert raw is None


def test_scraper_returns_empty_when_no_token(tmp_path, monkeypatch):
    monkeypatch.setattr("job_hunt.scrapers.gmail_inbox.TOKEN_PATH", tmp_path / "no_token.json")
    rows = GmailInboxScraper().run()
    assert rows == []


def test_scraper_with_mocked_service():
    # Mock _build_service to return a fake Gmail service whose list/get return canned data
    fake = MagicMock()
    fake.users().messages().list().execute.return_value = {"messages": [{"id": "m1"}], "nextPageToken": None}
    fake.users().messages().get().execute.return_value = {
        "id": "m1",
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": _b64("We're hiring engineers.")},
            "headers": [
                {"name": "From", "value": "recruiter@acme.com"},
                {"name": "Subject", "value": "Opportunity"},
                {"name": "Date", "value": "Mon, 26 May 2026 10:00:00 +0000"},
            ],
        },
    }

    s = GmailInboxScraper()
    with patch.object(s, "_build_service", return_value=fake):
        rows = s.run()
    assert len(rows) == 1
    assert rows[0].source == "gmail"
