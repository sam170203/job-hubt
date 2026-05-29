"""Gmail aggregator — pulls recruiter outreach + job alerts since last run.

Idempotent via the gmail_messages.msg_id unique key (already exists in schema from Plan 1).
Classifies each message into `parsed_signal`:
- 'recruiter_outreach' — From a recruiter, mentions a role.
- 'job_alert'          — LinkedIn/Wellfound/Indeed alerts.
- 'interview_invite'   — Subject mentions interview/scheduling.
- 'rejection'          — "not moving forward", "regret to inform".
- 'noise'              — anything else.

For 'recruiter_outreach' AND 'job_alert', emits RawJobs (source='gmail').
'interview_invite' and 'rejection' don't create jobs — they should later be wired to events.

NOTE: requires OAuth setup. Run scripts/setup_gmail.py first.
"""
from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from job_hunt.scrapers.base import RawJob
from job_hunt.settings import get_data_dir

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = get_data_dir() / ".gmail_token.json"
LOOKBACK_DAYS = 7
MAX_MESSAGES = 200

RECRUITER_DOMAINS = (
    "linkedin.com", "wellfound.com", "lever.co", "greenhouse.io",
    "ashbyhq.com", "workable.com", "smartrecruiters.com",
)
RECRUITER_HEADER_HINTS = ("recruiter", "talent", "people", "hiring")
ALERT_SUBJECT_HINTS = ("jobs for you", "new jobs", "your job alert", "matches you", "jobs alert")
INTERVIEW_HINTS = ("interview", "schedule a chat", "schedule a call")
REJECT_HINTS = ("not moving forward", "regret to inform", "we decided to move ahead",
                "we will not be moving", "filled the position", "unfortunately")


def _load_credentials() -> Credentials | None:
    if not TOKEN_PATH.exists():
        log.warning("Gmail token not found at %s — run scripts/setup_gmail.py first.",
                    TOKEN_PATH)
        return None
    return Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)


def _decode_part_body(part: dict) -> str:
    body = part.get("body", {}) or {}
    data = body.get("data")
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def extract_plain_text(payload: dict[str, Any]) -> str:
    """Flatten a Gmail payload to plain text."""
    mime = payload.get("mimeType", "")
    parts = payload.get("parts") or []

    if mime.startswith("text/plain"):
        return _decode_part_body(payload)
    if mime.startswith("text/html"):
        # fallback if no plain text part exists
        html = _decode_part_body(payload)
        return re.sub(r"<[^>]+>", " ", html)
    if parts:
        # Prefer text/plain; fall back to first text/html
        for p in parts:
            if p.get("mimeType", "").startswith("text/plain"):
                t = extract_plain_text(p)
                if t:
                    return t
        for p in parts:
            if p.get("mimeType", "").startswith("text/html"):
                return extract_plain_text(p)
        for p in parts:
            t = extract_plain_text(p)
            if t:
                return t
    return ""


def _header(msg: dict, name: str) -> str:
    headers = msg.get("payload", {}).get("headers", []) or []
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "") or ""
    return ""


def classify(from_addr: str, subject: str, body: str) -> str:
    fa = from_addr.lower()
    s = subject.lower()
    b = body.lower()

    if any(h in s for h in INTERVIEW_HINTS):
        return "interview_invite"
    if any(h in s for h in REJECT_HINTS) or any(h in b[:1000] for h in REJECT_HINTS):
        return "rejection"
    if any(h in s for h in ALERT_SUBJECT_HINTS) or any(d in fa for d in RECRUITER_DOMAINS):
        return "job_alert"
    if any(h in fa for h in RECRUITER_HEADER_HINTS) or "recruit" in fa:
        return "recruiter_outreach"
    return "noise"


def message_to_raw(msg: dict) -> tuple[str, RawJob | None]:
    """Return (signal, RawJob or None).

    Only recruiter_outreach + job_alert emit a RawJob. The signal is always returned
    so the caller can persist a gmail_messages row for idempotency + audit.
    """
    msg_id = msg.get("id") or ""
    subject = _header(msg, "Subject")
    from_addr = _header(msg, "From")
    body = extract_plain_text(msg.get("payload", {}) or {})
    date_str = _header(msg, "Date")
    try:
        received_at = parsedate_to_datetime(date_str).replace(tzinfo=None) if date_str else None
    except Exception:
        received_at = None

    signal = classify(from_addr, subject, body)

    if signal in ("recruiter_outreach", "job_alert"):
        return signal, RawJob(
            source="gmail",
            external_id=msg_id,
            payload={
                "msg_id": msg_id,
                "from_addr": from_addr,
                "subject": subject,
                "received_at": received_at.isoformat() if received_at else None,
                "body_excerpt": body[:5000],
                "signal": signal,
            },
        )
    return signal, None


class GmailInboxScraper:
    source = "gmail"

    def __init__(self, lookback_days: int = LOOKBACK_DAYS, max_messages: int = MAX_MESSAGES):
        self.lookback_days = lookback_days
        self.max_messages = max_messages

    def _build_service(self):
        creds = _load_credentials()
        if creds is None:
            return None
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def _list_message_ids(self, service) -> list[str]:
        cutoff = (datetime.utcnow() - timedelta(days=self.lookback_days)).strftime("%Y/%m/%d")
        q = f"after:{cutoff}"
        ids: list[str] = []
        page_token: str | None = None
        while True:
            kwargs = {"userId": "me", "q": q, "maxResults": 100}
            if page_token:
                kwargs["pageToken"] = page_token
            resp = service.users().messages().list(**kwargs).execute()
            for m in resp.get("messages", []) or []:
                ids.append(m["id"])
                if len(ids) >= self.max_messages:
                    return ids
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return ids

    def _get_message(self, service, msg_id: str) -> dict | None:
        try:
            return service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except Exception as e:
            log.warning("Gmail get failed for msg=%s: %s", msg_id, e)
            return None

    def run(self) -> list[RawJob]:
        service = self._build_service()
        if service is None:
            log.warning("Gmail not configured; scraper returning 0 rows.")
            return []

        try:
            msg_ids = self._list_message_ids(service)
        except Exception as e:
            log.warning("Gmail list failed: %s", e)
            return []

        out: list[RawJob] = []
        for mid in msg_ids:
            msg = self._get_message(service, mid)
            if msg is None:
                continue
            _, raw = message_to_raw(msg)
            if raw is not None:
                out.append(raw)
        return out
