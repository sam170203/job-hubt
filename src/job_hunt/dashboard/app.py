"""Streamlit dashboard — Inbox page (v2).

Run: `uv run streamlit run src/job_hunt/dashboard/app.py`

Pages:
- This file → Inbox
- pages/2_Applied.py → Applied
"""

from __future__ import annotations

import streamlit as st
import yaml

from job_hunt.dashboard.queries import (
    apply_to_job,
    blocklist_company,
    distinct_filter_values,
    get_inbox_jobs,
    list_saved_views,
    save_view,
    set_job_status,
)
from job_hunt.settings import PROJECT_ROOT

st.set_page_config(page_title="Job Hunt — Inbox", layout="wide")

st.title("Inbox")
st.caption("Targeted: filters by work mode, geography, company tier, and skills you actually have.")


@st.cache_data(ttl=60)
def _resume_variants() -> list[str]:
    path = PROJECT_ROOT / "config" / "resume_variants.yaml"
    if not path.exists():
        return ["ai-ml", "swe-startup"]
    data = yaml.safe_load(path.read_text()) or {}
    return list((data.get("variants") or {}).keys()) or ["ai-ml"]


@st.cache_data(ttl=60)
def _my_skills() -> list[str]:
    path = PROJECT_ROOT / "config" / "my_skills.yaml"
    data = yaml.safe_load(path.read_text()) or {}
    skills = data.get("my_skills", {})
    out: set[str] = set()
    for bucket in ("strong", "moderate", "learning"):
        for s in skills.get(bucket, []):
            out.add(s)
    return sorted(out)


CHANNELS = ["direct", "referral", "email", "linkedin", "x_dm", "other"]


with st.sidebar:
    st.header("Saved views")
    views = list_saved_views()
    view_names = ["(none)"] + [v.name for v in views]
    chosen_view = st.selectbox("Load view", view_names, index=0)
    loaded: dict = {}
    if chosen_view != "(none)":
        loaded = next((v.filters_json for v in views if v.name == chosen_view), {}) or {}

    st.header("Filters")
    filters = distinct_filter_values()

    sel_work = st.multiselect(
        "Work mode", filters["work_modes"], default=loaded.get("work_modes", [])
    )
    geo_choice = st.radio(
        "Geography",
        ["Either", "India", "International"],
        index=["Either", "India", "International"].index(loaded.get("geo_choice", "Either")),
    )
    if geo_choice == "India":
        india_states = [s for s in filters["india_states"]]
        sel_states = st.multiselect(
            "India state", india_states, default=loaded.get("india_states", [])
        )
    else:
        sel_states = []
    sel_tiers = st.multiselect(
        "Company tier", filters["company_tiers"], default=loaded.get("company_tiers", [])
    )
    sel_skills = st.multiselect(
        "Required skill (any of)", _my_skills(), default=loaded.get("required_skills", [])
    )
    min_score = st.slider(
        "Min match score", 0.0, 1.0, loaded.get("min_match_score", 0.0), step=0.05
    )

    st.divider()
    sel_sources = st.multiselect("Source", filters["sources"], default=loaded.get("sources", []))
    sel_roles = st.multiselect(
        "Role tag", filters["role_tags"], default=loaded.get("role_tags", [])
    )
    sel_seniority = st.multiselect(
        "Seniority", filters["seniority_tags"], default=loaded.get("seniority_tags", [])
    )
    days = st.slider("Within (days)", 1, 30, loaded.get("within_days", 7))

    st.divider()
    new_view_name = st.text_input("Save current filters as…")
    if st.button("Save view", disabled=not new_view_name.strip()):
        save_view(
            new_view_name.strip(),
            {
                "work_modes": sel_work,
                "geo_choice": geo_choice,
                "india_states": sel_states,
                "company_tiers": sel_tiers,
                "required_skills": sel_skills,
                "min_match_score": min_score,
                "sources": sel_sources,
                "role_tags": sel_roles,
                "seniority_tags": sel_seniority,
                "within_days": days,
            },
        )
        st.success(f"Saved '{new_view_name.strip()}'")
        st.rerun()

countries = None
if geo_choice == "India":
    countries = ["India"]
elif geo_choice == "International":
    countries = [c for c in filters["countries"] if c != "India"]

jobs = get_inbox_jobs(
    role_tags=sel_roles or None,
    sources=sel_sources or None,
    seniority_tags=sel_seniority or None,
    work_modes=sel_work or None,
    countries=countries,
    india_states=sel_states or None,
    company_tiers=sel_tiers or None,
    required_skills=sel_skills or None,
    min_match_score=min_score or None,
    within_days=days,
)

st.write(f"**{len(jobs)} jobs**")

for j in jobs:
    with st.container(border=True):
        head_cols = st.columns([4, 1])
        with head_cols[0]:
            score_badge = f" `match {j.match_score:.0%}`" if j.match_score is not None else ""
            st.markdown(f"**{j.company}** — {j.title}{score_badge}")
            meta_parts = [
                j.location,
                j.role_tag,
                j.seniority_tag,
                j.work_mode,
                j.company_tier,
                j.source,
            ]
            meta = " · ".join(p for p in meta_parts if p)
            st.caption(meta)
            if j.tech_tags:
                st.caption("Tech: " + ", ".join(j.tech_tags))
            st.markdown(f"[Open link]({j.url})")
            if j.jd_text:
                with st.expander("JD excerpt"):
                    excerpt = j.jd_text[:1200] + ("…" if len(j.jd_text) > 1200 else "")
                    st.write(excerpt)
        with head_cols[1]:
            with st.popover("Apply ✉️"):
                st.write(f"Applying to **{j.company}** — {j.title}")
                rv = st.selectbox("Resume variant", _resume_variants(), key=f"rv_{j.id}")
                ch = st.selectbox("Channel", CHANNELS, key=f"ch_{j.id}")
                note = st.text_input("Note (optional)", key=f"nt_{j.id}")
                if st.button("Confirm apply", key=f"apply_{j.id}"):
                    apply_to_job(j.id, resume_variant=rv, channel=ch, note=note or None)
                    st.success("Logged. Check Applied page.")
                    st.rerun()
            if st.button("Shortlist", key=f"sl_{j.id}"):
                set_job_status(j.id, "shortlisted")
                st.rerun()
            if st.button("Skip", key=f"sk_{j.id}"):
                set_job_status(j.id, "skipped")
                st.rerun()
            if st.button(f"🚫 Hide all {j.company}", key=f"bl_{j.id}"):
                blocklist_company(j.company, reason="hidden from inbox")
                st.rerun()
