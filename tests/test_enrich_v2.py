from job_hunt.pipeline.enrich import (
    classify_company_tier,
    classify_work_mode,
    compute_match_score,
    extract_country_and_state,
    load_my_skills,
)


def test_work_mode_remote():
    assert classify_work_mode("Senior ML Engineer (Remote)", "100% remote, work from anywhere") == "remote"


def test_work_mode_hybrid():
    assert classify_work_mode("Engineer", "Hybrid: 3 days in office") == "hybrid"


def test_work_mode_onsite():
    assert classify_work_mode("Engineer", "Onsite in HQ, no remote") == "onsite"


def test_work_mode_unknown():
    assert classify_work_mode("Engineer", "Build cool stuff") == "unknown"


def test_country_india_state_bangalore():
    country, state = extract_country_and_state("Bangalore, India")
    assert country == "India"
    assert state == "Karnataka"


def test_country_india_state_delhi_substring():
    country, state = extract_country_and_state("New Delhi - hybrid")
    assert country == "India"
    assert state == "Delhi"


def test_country_unknown():
    country, state = extract_country_and_state("Berlin, Germany")
    assert country == "Germany"
    assert state is None


def test_country_remote_only():
    country, state = extract_country_and_state("Remote")
    assert country == "International (unclear)"
    assert state is None


def test_company_tier_mnc_by_name():
    assert classify_company_tier("Google", "We build ads") == "mnc"


def test_company_tier_startup_by_jd():
    assert classify_company_tier("Acme", "We are an early-stage YC startup") == "startup"


def test_company_tier_unknown():
    assert classify_company_tier("Acme", "We build things") == "unknown"


def test_match_score_perfect():
    score = compute_match_score(["python", "pytorch"], {"python", "pytorch"})
    assert score == 1.0


def test_match_score_partial():
    score = compute_match_score(["python", "rust"], {"python"})
    assert score == 0.5


def test_match_score_none():
    score = compute_match_score(["rust"], {"python"})
    assert score == 0.0


def test_match_score_empty_jd():
    score = compute_match_score([], {"python"})
    assert score == 0.0


def test_load_my_skills_returns_set():
    s = load_my_skills()
    assert isinstance(s, set)
    assert "python" in s  # from my_skills.yaml
