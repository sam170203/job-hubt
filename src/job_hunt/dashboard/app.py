"""Streamlit dashboard — Inbox page (v1).

Run: `uv run streamlit run src/job_hunt/dashboard/app.py`

The Pipeline, Analytics, and Today pages land in Plans 3 & 4.
"""

from __future__ import annotations

import streamlit as st

from job_hunt.dashboard.queries import (
    distinct_filter_values,
    get_inbox_jobs,
    set_job_status,
)

st.set_page_config(page_title="Job Hunt — Inbox", layout="wide")

st.title("Inbox")
st.caption(
    "New jobs from the last 7 days. Shortlist or skip — applied/rejected happen on the "
    "Pipeline page (Plan 3)."
)

with st.sidebar:
    st.header("Filters")
    filters = distinct_filter_values()
    sel_sources = st.multiselect("Source", filters["sources"])
    sel_roles = st.multiselect("Role tag", filters["role_tags"])
    sel_seniority = st.multiselect("Seniority", filters["seniority_tags"])
    days = st.slider("Within (days)", min_value=1, max_value=30, value=7)

jobs = get_inbox_jobs(
    role_tags=sel_roles or None,
    sources=sel_sources or None,
    seniority_tags=sel_seniority or None,
    within_days=days,
)

st.write(f"**{len(jobs)} jobs**")

for j in jobs:
    with st.container(border=True):
        cols = st.columns([4, 1, 1])
        with cols[0]:
            st.markdown(f"**{j.company}** — {j.title}")
            meta_parts = [j.location, j.role_tag, j.seniority_tag, j.source]
            meta = " · ".join(p for p in meta_parts if p)
            st.caption(meta)
            if j.tech_tags:
                st.caption("Tech: " + ", ".join(j.tech_tags))
            st.markdown(f"[Open link]({j.url})")
            if j.jd_text:
                with st.expander("JD excerpt"):
                    excerpt = j.jd_text[:1200] + ("…" if len(j.jd_text) > 1200 else "")
                    st.write(excerpt)
        with cols[1]:
            if st.button("Shortlist", key=f"sl_{j.id}"):
                set_job_status(j.id, "shortlisted")
                st.rerun()
        with cols[2]:
            if st.button("Skip", key=f"sk_{j.id}"):
                set_job_status(j.id, "skipped")
                st.rerun()
