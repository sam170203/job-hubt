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
