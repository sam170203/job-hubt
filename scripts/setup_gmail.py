"""One-time Gmail OAuth setup.

Steps for the user (documented in README):
1. Create a Google Cloud project at https://console.cloud.google.com.
2. Enable the Gmail API.
3. Create an OAuth 2.0 Client ID (type: Desktop App).
4. Download the client_secret_*.json file.
5. Set GMAIL_CLIENT_SECRETS_PATH in .env to point at it.
6. Run: uv run python scripts/setup_gmail.py
7. Browser opens; sign in and grant read-only Gmail access.
8. Token saved to data/.gmail_token.json (gitignored).

Re-run only if you revoke access or want to re-auth.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from job_hunt.settings import get_data_dir

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = get_data_dir() / ".gmail_token.json"


def main() -> int:
    client_secrets = os.environ.get("GMAIL_CLIENT_SECRETS_PATH", "").strip()
    if not client_secrets:
        print(
            "ERROR: Set GMAIL_CLIENT_SECRETS_PATH in .env to your "
            "downloaded client_secret_*.json path.",
            file=sys.stderr,
        )
        return 1
    if not Path(client_secrets).exists():
        print(f"ERROR: {client_secrets} does not exist.", file=sys.stderr)
        return 1

    get_data_dir().mkdir(parents=True, exist_ok=True)

    creds: Credentials | None = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
        # tighten perms
        os.chmod(TOKEN_PATH, 0o600)

    print(f"OK. Token saved at {TOKEN_PATH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
