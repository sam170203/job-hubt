"""Rule-based enrichment: assign role_tag, seniority_tag, tech_tags from keywords.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from job_hunt.settings import PROJECT_ROOT


@dataclass
class EnrichedTags:
    role_tag: str | None = None
    seniority_tag: str | None = None
    tech_tags: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def _load_keywords() -> dict:
    path: Path = PROJECT_ROOT / "config" / "keywords.yaml"
    with path.open() as f:
        return yaml.safe_load(f)


def _first_tag_match(haystack: str, mapping: dict[str, list[str]]) -> str | None:
    for tag, needles in mapping.items():
        for n in needles:
            if n.lower() in haystack:
                return tag
    return None


def _all_tag_matches(haystack: str, mapping: dict[str, list[str]]) -> list[str]:
    out = []
    for tag, needles in mapping.items():
        if any(n.lower() in haystack for n in needles):
            out.append(tag)
    return out


def enrich_tags(title: str, jd_text: str | None) -> EnrichedTags:
    keywords = _load_keywords()
    haystack = f"{title or ''} {jd_text or ''}".lower()

    return EnrichedTags(
        role_tag=_first_tag_match(haystack, keywords.get("role_tag", {})),
        seniority_tag=_first_tag_match(haystack, keywords.get("seniority_tag", {})),
        tech_tags=_all_tag_matches(haystack, keywords.get("tech_tags", {})),
    )


# --- v2 enrichers (work_mode, geography, company_tier, match_score) ---


@lru_cache(maxsize=None)
def _load_yaml(name: str) -> dict:
    path = PROJECT_ROOT / "config" / name
    with path.open() as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def load_my_skills() -> set[str]:
    data = _load_yaml("my_skills.yaml")
    skills = data.get("my_skills", {})
    out: set[str] = set()
    for bucket in ("strong", "moderate", "learning"):
        for s in skills.get(bucket, []):
            out.add(s.lower())
    return out


@lru_cache(maxsize=1)
def _work_mode_rules() -> dict[str, list[str]]:
    return _load_yaml("work_mode_keywords.yaml").get("work_mode", {})


def classify_work_mode(title: str, jd_text: str | None) -> str:
    haystack = f"{title or ''} {jd_text or ''}".lower()
    rules = _work_mode_rules()
    # Check hybrid before onsite (so "3 days in office" in a hybrid context wins),
    # and onsite before remote so "no remote" doesn't match as remote first.
    for mode in ("hybrid", "onsite", "remote"):
        needles = rules.get(mode, [])
        for n in needles:
            if n.lower() in haystack:
                return mode
    return "unknown"


@lru_cache(maxsize=1)
def _india_states() -> dict[str, list[str]]:
    return _load_yaml("india_states.yaml").get("india_states", {})


# Country detector — minimal hardcoded list; falls back to International (unclear).
COUNTRY_KEYWORDS = {
    "India": ["india"],
    "USA": ["usa", "united states", "u.s.", "u.s.a", "remote us", "remote (us)"],
    "UK": ["united kingdom", "uk", "england", "london"],
    "Germany": ["germany", "berlin", "munich"],
    "Canada": ["canada", "toronto", "vancouver"],
    "Singapore": ["singapore"],
    "Australia": ["australia", "sydney", "melbourne"],
    "Netherlands": ["netherlands", "amsterdam"],
    "France": ["france", "paris"],
    "Switzerland": ["switzerland", "zurich"],
}


def extract_country_and_state(location: str | None) -> tuple[str | None, str | None]:
    if not location:
        return ("International (unclear)", None)
    loc_lower = location.lower()

    # Detect India + state first (most specific).
    for state, needles in _india_states().items():
        for n in needles:
            if n.lower() in loc_lower:
                return ("India", state)

    # Other countries
    for country, needles in COUNTRY_KEYWORDS.items():
        for n in needles:
            if n.lower() in loc_lower:
                return (country, None)

    # If "remote" appears but no country → International (unclear)
    if "remote" in loc_lower or "anywhere" in loc_lower:
        return ("International (unclear)", None)

    # Fallback — pass the location string back as the country (best effort)
    return (location.strip()[:64], None)


@lru_cache(maxsize=1)
def _mnc_names() -> list[str]:
    return [n.lower() for n in _load_yaml("mnc_list.yaml").get("mncs", [])]


@lru_cache(maxsize=1)
def _company_tier_keywords() -> dict:
    return _load_yaml("company_tier_keywords.yaml")


def classify_company_tier(company: str, jd_text: str | None) -> str:
    name_lower = (company or "").lower()
    for mnc in _mnc_names():
        if mnc in name_lower:
            return "mnc"

    haystack = f"{company or ''} {jd_text or ''}".lower()
    kw = _company_tier_keywords()
    if any(k.lower() in haystack for k in kw.get("mnc_signals", [])):
        return "mnc"
    if any(k.lower() in haystack for k in kw.get("scaleup_signals", [])):
        return "scaleup"
    if any(k.lower() in haystack for k in kw.get("startup_signals", [])):
        return "startup"
    return "unknown"


def compute_match_score(jd_tech_tags: list[str] | None, my_skills: set[str]) -> float:
    if not jd_tech_tags:
        return 0.0
    overlap = sum(1 for t in jd_tech_tags if t.lower() in my_skills)
    return round(overlap / len(jd_tech_tags), 3)
