"""Applied page — what you've applied to, with follow-up flagging + CSV export."""
from __future__ import annotations

import csv
import io
from datetime import datetime

import streamlit as st

from job_hunt.dashboard.queries import list_applied_jobs, set_job_status

STATUS_OPTIONS = ["applied", "replied", "interviewing", "rejected", "ghosted", "offer"]
FOLLOW_UP_DAYS = 14


st.set_page_config(page_title="Job Hunt — Applied", layout="wide")
st.title("Applied")
st.caption(f"Follow-up suggested after {FOLLOW_UP_DAYS} days with no reply.")

jobs = list_applied_jobs()
st.write(f"**{len(jobs)} applications**")


def _latest_apply(j):
    if not j.applications:
        return None
    return max(j.applications, key=lambda a: a.applied_at)


def _days_since(d):
    if d is None:
        return None
    return (datetime.utcnow() - d).days


# CSV export
csv_buffer = io.StringIO()
writer = csv.writer(csv_buffer)
writer.writerow(["company", "title", "applied_at", "resume_variant", "channel",
                 "status", "days_since_apply", "url"])
for j in jobs:
    a = _latest_apply(j)
    writer.writerow([
        j.company, j.title,
        a.applied_at.isoformat() if a else "",
        a.resume_variant if a else "",
        a.channel if a else "",
        j.status,
        _days_since(a.applied_at if a else None),
        j.url,
    ])
st.download_button(
    "Download CSV",
    csv_buffer.getvalue(),
    file_name=f"applications_{datetime.utcnow().strftime('%Y-%m-%d')}.csv",
    mime="text/csv",
)

for j in jobs:
    a = _latest_apply(j)
    days = _days_since(a.applied_at if a else None)
    needs_followup = j.status == "applied" and days is not None and days >= FOLLOW_UP_DAYS
    border_color = "🔴" if needs_followup else ("🟢" if j.status in {"offer", "interviewing"} else "⚪")

    with st.container(border=True):
        cols = st.columns([4, 1])
        with cols[0]:
            st.markdown(f"{border_color} **{j.company}** — {j.title}")
            meta = []
            if a:
                meta.append(f"applied {a.applied_at.strftime('%Y-%m-%d')}")
                if days is not None:
                    meta.append(f"{days} days ago")
                if a.resume_variant:
                    meta.append(f"resume: {a.resume_variant}")
                if a.channel:
                    meta.append(f"via {a.channel}")
            meta.append(f"status: {j.status}")
            st.caption(" · ".join(meta))
            st.markdown(f"[Open link]({j.url})")
            if needs_followup:
                st.warning(f"No reply in {days} days — consider following up.")
        with cols[1]:
            new_status = st.selectbox(
                "Status",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(j.status) if j.status in STATUS_OPTIONS else 0,
                key=f"st_{j.id}",
            )
            if new_status != j.status:
                if st.button("Update", key=f"upd_{j.id}"):
                    set_job_status(j.id, new_status)
                    st.rerun()
