from unittest.mock import patch

from job_hunt.scrapers.wellfound import (
    WellfoundScraper,
    fetch_sitemap_urls,
    job_ld_to_raw,
    parse_job_page,
)


SAMPLE_SITEMAP_INDEX = """<?xml version="1.0"?>
<sitemapindex>
  <sitemap><loc>https://wellfound.com/sitemap/jobs/jobs1.xml</loc></sitemap>
  <sitemap><loc>https://wellfound.com/sitemap/companies/c1.xml</loc></sitemap>
</sitemapindex>
""".encode()

SAMPLE_JOBS_SITEMAP = """<?xml version="1.0"?>
<urlset>
  <url><loc>https://wellfound.com/jobs/123-ml-engineer</loc></url>
  <url><loc>https://wellfound.com/jobs/456-backend</loc></url>
  <url><loc>https://wellfound.com/companies/acme</loc></url>
</urlset>
""".encode()


SAMPLE_JOB_HTML = """
<html><head>
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"JobPosting","title":"ML Engineer",
   "hiringOrganization":{"name":"Acme"},"description":"Build cool stuff",
   "jobLocation":{"address":{"addressLocality":"Bangalore","addressCountry":"IN"}}}
  </script>
</head><body></body></html>
"""


class FakeResp:
    def __init__(self, content: bytes, text: str = "", status: int = 200):
        self.content = content
        self.text = text or content.decode("utf-8", errors="ignore")
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP error")


def test_parse_job_page_extracts_ld_json():
    ld = parse_job_page(SAMPLE_JOB_HTML, "https://wellfound.com/jobs/123-ml-engineer")
    assert ld is not None
    assert ld["title"] == "ML Engineer"


def test_parse_job_page_returns_none_when_no_ld():
    assert parse_job_page("<html><body>no script</body></html>", "x") is None


def test_job_ld_to_raw():
    raw = job_ld_to_raw(
        "https://wellfound.com/jobs/123-ml-engineer",
        {"@type": "JobPosting", "title": "ML"},
    )
    assert raw.source == "wellfound"
    assert raw.external_id.startswith("-jobs-123-ml-engineer")
    assert raw.payload["job_ld"]["title"] == "ML"


def test_fetch_sitemap_urls_follows_index():
    def fake_get(url, timeout=None, follow_redirects=None, headers=None):
        if "sitemap.xml" in url and "jobs1" not in url:
            return FakeResp(SAMPLE_SITEMAP_INDEX)
        if "jobs1.xml" in url:
            return FakeResp(SAMPLE_JOBS_SITEMAP)
        raise Exception("unexpected url: " + url)

    with patch("job_hunt.scrapers.wellfound.httpx.get", side_effect=fake_get):
        urls = fetch_sitemap_urls()
    assert any("/jobs/123-ml-engineer" in u for u in urls)
    # Companies URL should be filtered out
    assert not any("/companies/" in u for u in urls)


def test_fetch_sitemap_urls_empty_on_http_error():
    def boom(*a, **kw):
        raise Exception("blocked")
    with patch("job_hunt.scrapers.wellfound.httpx.get", side_effect=boom):
        assert fetch_sitemap_urls() == []


def test_scraper_run_with_mocks():
    def fake_get(url, timeout=None, follow_redirects=None, headers=None):
        if url == "https://wellfound.com/sitemap.xml":
            return FakeResp(SAMPLE_SITEMAP_INDEX)
        if "jobs1.xml" in url:
            return FakeResp(SAMPLE_JOBS_SITEMAP)
        if "/jobs/" in url:
            return FakeResp(SAMPLE_JOB_HTML.encode(), text=SAMPLE_JOB_HTML)
        return FakeResp(b"")

    with patch("job_hunt.scrapers.wellfound.httpx.get", side_effect=fake_get), \
         patch("job_hunt.scrapers.wellfound.time.sleep", lambda *_: None):
        rows = WellfoundScraper().run()

    assert len(rows) == 2  # 2 job urls in the sample sitemap
    assert all(r.source == "wellfound" for r in rows)
