from unittest.mock import patch

from job_hunt.scrapers.x_search import (
    XSearchScraper,
    parse_nitter_search,
    tweet_to_raw,
)


SAMPLE_NITTER_HTML = """
<html><body>
  <div class="timeline-item">
    <a class="tweet-link" href="/founder1/status/1234567890"></a>
    <a class="username">@founder1</a>
    <span class="tweet-date"><a title="May 26, 2026 · 10:00 UTC"></a></span>
    <div class="tweet-content">We are hiring ML engineers in Bangalore. Apply: https://acme.io/jobs</div>
  </div>
  <div class="timeline-item">
    <a class="tweet-link" href="/founder2/status/9876543210"></a>
    <a class="username">@founder2</a>
    <span class="tweet-date"><a title="May 25, 2026"></a></span>
    <div class="tweet-content">hiring senior backend india</div>
  </div>
  <div class="timeline-item">
    <a class="tweet-link" href="/badone/conversation/x"></a>
    <div class="tweet-content">no status id</div>
  </div>
</body></html>
"""


def test_parse_nitter_search_extracts_tweets():
    tweets = parse_nitter_search(SAMPLE_NITTER_HTML, "hiring ML India")
    assert len(tweets) == 2
    assert tweets[0]["id"] == "1234567890"
    assert "hiring ML engineers" in tweets[0]["text"]
    assert tweets[1]["id"] == "9876543210"


def test_tweet_to_raw():
    raw = tweet_to_raw({"id": "111", "url": "u", "text": "t",
                        "author": "a", "date": None, "query": "q"})
    assert raw.source == "x"
    assert raw.external_id == "111"


def test_scraper_returns_empty_when_no_queries(monkeypatch, caplog):
    monkeypatch.setattr("job_hunt.scrapers.x_search._load_queries", lambda: [])
    rows = XSearchScraper().run()
    assert rows == []


def test_scraper_returns_empty_when_no_instance(monkeypatch):
    monkeypatch.setattr("job_hunt.scrapers.x_search._load_queries", lambda: ["q1"])
    monkeypatch.setattr("job_hunt.scrapers.x_search._pick_live_instance", lambda: None)
    rows = XSearchScraper().run()
    assert rows == []


def test_scraper_happy_path(monkeypatch):
    monkeypatch.setattr("job_hunt.scrapers.x_search._load_queries",
                        lambda: ["hiring ML India"])
    monkeypatch.setattr("job_hunt.scrapers.x_search._pick_live_instance",
                        lambda: "https://nitter.test")
    monkeypatch.setattr("job_hunt.scrapers.x_search.time.sleep", lambda *_: None)

    class FakeResp:
        status_code = 200
        text = SAMPLE_NITTER_HTML

    monkeypatch.setattr("job_hunt.scrapers.x_search._try_get", lambda u: FakeResp())

    rows = XSearchScraper().run()
    assert len(rows) == 2
    assert {r.external_id for r in rows} == {"1234567890", "9876543210"}
