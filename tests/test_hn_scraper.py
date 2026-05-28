import json
from pathlib import Path
from unittest.mock import patch

from job_hunt.scrapers.hn_hiring import HNHiringScraper, parse_comment_to_raw


FIXTURE = Path(__file__).parent / "fixtures" / "hn_hiring_sample.json"


def test_parse_comment_returns_none_for_empty_text():
    out = parse_comment_to_raw({"id": 1, "text": None, "author": "x"})
    assert out is None


def test_parse_comment_extracts_text_and_id():
    comment = {
        "id": 42,
        "author": "founder",
        "text": "Acme Corp | ML Engineer | Remote | Apply: https://acme.io/jobs",
    }
    raw = parse_comment_to_raw(comment)
    assert raw is not None
    assert raw.source == "hn"
    assert raw.external_id == "42"
    assert "Acme" in raw.payload["text"]
    assert raw.payload["author"] == "founder"


def test_scraper_run_uses_fixture():
    """Patch httpx so the scraper runs against the local fixture, not the network."""
    fixture = json.loads(FIXTURE.read_text())

    class FakeResp:
        def __init__(self, data):
            self._data = data
        def json(self):
            return self._data
        def raise_for_status(self):
            pass

    def fake_get(url, params=None, **_):
        if "search" in url:
            return FakeResp({"hits": [{"objectID": fixture["id"]}]})
        return FakeResp(fixture)

    with patch("job_hunt.scrapers.hn_hiring.httpx.get", side_effect=fake_get):
        rows = HNHiringScraper().run()

    text_children = [c for c in fixture["children"] if c.get("text")]
    assert len(rows) == len(text_children)
    assert all(r.source == "hn" for r in rows)
