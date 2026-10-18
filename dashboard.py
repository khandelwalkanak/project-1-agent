"""
Streamlit dashboard — shows all past reports from the reports/ folder.

Run locally:   uv run --extra dashboard streamlit run dashboard.py
Deploy free:   https://share.streamlit.io  (connect GitHub repo, set file = dashboard.py)
"""

import re
from datetime import datetime
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Social Trends Agent",
    page_icon="📡",
    layout="wide",
)

REPORTS_DIR = Path("reports")


def _timestamp_to_label(path: Path) -> str:
    """report_1792332011.md → '2026-10-19 07:00'"""
    m = re.search(r"(\d{9,10})", path.stem)
    if m:
        try:
            return datetime.fromtimestamp(int(m.group(1))).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
    return path.stem


# ── Load reports ──────────────────────────────────────────────────────────────

report_files = sorted(
    [f for f in REPORTS_DIR.glob("*.md") if f.name != ".gitkeep"],
    reverse=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Social Trends Agent")
    st.caption("Meta (Ray-Ban) Smart Glasses · India Content Ideas")
    st.divider()

    if not report_files:
        st.warning("No reports yet. Run the agent to generate one.")
        st.code("uv run python main.py")
        st.stop()

    st.metric("Total reports", len(report_files))
    st.metric("Latest run", _timestamp_to_label(report_files[0]))

    st.divider()
    st.subheader("Report history")
    labels = [_timestamp_to_label(f) for f in report_files]
    selected_idx = st.radio(
        "Select a report",
        range(len(report_files)),
        format_func=lambda i: labels[i],
        label_visibility="collapsed",
    )

# ── Main: render selected report ─────────────────────────────────────────────

selected_path = report_files[selected_idx]
content = selected_path.read_text(encoding="utf-8")

st.markdown(content, unsafe_allow_html=False)
