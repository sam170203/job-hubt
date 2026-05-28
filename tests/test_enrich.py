from job_hunt.pipeline.enrich import enrich_tags


def test_role_ml_detected():
    tags = enrich_tags(title="ML Engineer (Remote)", jd_text="Build models with PyTorch")
    assert tags.role_tag == "ml"


def test_role_first_match_wins():
    tags = enrich_tags(title="ML / Software Engineer", jd_text="")
    assert tags.role_tag == "ml"


def test_seniority_intern():
    tags = enrich_tags(title="Summer Intern – Backend", jd_text="")
    assert tags.seniority_tag == "intern"


def test_seniority_senior():
    tags = enrich_tags(title="Senior Platform Engineer", jd_text="Lead the team")
    assert tags.seniority_tag == "senior"


def test_tech_tags_multi():
    tags = enrich_tags(title="ML Engineer", jd_text="Python, PyTorch, LangChain, AWS")
    assert set(tags.tech_tags) >= {"python", "pytorch", "langchain", "aws"}


def test_no_match_returns_none_tags():
    tags = enrich_tags(title="Pottery Apprentice", jd_text="Throw clay")
    assert tags.role_tag is None
    assert tags.seniority_tag is None
    assert tags.tech_tags == []
