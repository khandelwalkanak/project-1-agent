"""
Streamlit dashboard — social trends reports viewer.

Run locally:   uv run --extra dashboard streamlit run dashboard.py
Deploy:        https://share.streamlit.io
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

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Metric cards */
div[data-testid="metric-container"] {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 18px 20px !important;
}
div[data-testid="metric-container"] label {
    color: #64748b !important;
    font-size: 0.8em !important;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 2em !important;
    color: #1d4ed8 !important;
    font-weight: 700 !important;
}

/* Badges */
.badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 0.76em;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
}
.badge-SAME       { background: #dbeafe; color: #1d4ed8; }
.badge-TWIST      { background: #fed7aa; color: #c2410c; }
.badge-WHITESPACE { background: #bbf7d0; color: #15803d; }
.badge-low        { background: #bbf7d0; color: #15803d; }
.badge-med        { background: #fef08a; color: #92400e; }
.badge-high       { background: #fecaca; color: #b91c1c; }

/* 3-second hook callout */
.hook-box {
    background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%);
    border-left: 4px solid #3b82f6;
    padding: 12px 18px;
    border-radius: 0 10px 10px 0;
    font-style: italic;
    color: #1e40af;
    margin: 10px 0 14px 0;
    line-height: 1.6;
    font-size: 0.95em;
}

/* Why it works */
.why-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px 16px;
    color: #475569;
    font-size: 0.88em;
    line-height: 1.6;
    margin-top: 6px;
}

/* Hashtags */
.hashtags {
    color: #6366f1;
    font-size: 0.82em;
    line-height: 1.8;
}

/* Section headings */
.section-heading {
    font-size: 1.05em;
    font-weight: 700;
    color: #0f172a;
    margin: 28px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #e2e8f0;
    letter-spacing: 0.3px;
}

/* Report header */
.report-header {
    background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 100%);
    border-radius: 14px;
    padding: 28px 32px;
    margin-bottom: 24px;
    color: white;
}
.report-header h1 {
    margin: 0 0 6px 0;
    font-size: 1.7em;
    font-weight: 800;
    color: white;
}
.report-header .sub {
    color: #bfdbfe;
    font-size: 0.9em;
}
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _timestamp_to_label(path: Path) -> str:
    m = re.search(r"(\d{9,10})", path.stem)
    if m:
        try:
            return datetime.fromtimestamp(int(m.group(1))).strftime("%b %d, %Y  %H:%M")
        except Exception:
            pass
    return path.stem


def _badge(text: str, kind: str) -> str:
    key = text.strip().upper().replace(" ", "")
    cls = f"badge-{key}" if f"badge-{key}" in (
        "badge-SAME badge-TWIST badge-WHITESPACE "
        "badge-low badge-med badge-high"
    ) else "badge-SAME"
    return f'<span class="badge {cls}">{text.strip()}</span>'


def _parse(content: str) -> dict:
    """Extract structured sections from the report markdown."""
    out = {
        "title": "Meta Smart Glasses — India Content Ideas",
        "date": "",
        "themes": [],
        "ideas": [],
        "stats": {},
    }

    title_m = re.search(r"^# (.+)$", content, re.MULTILINE)
    if title_m:
        out["title"] = title_m.group(1).strip()

    date_m = re.search(r"_Report date:\s*(.+?)_", content)
    if date_m:
        out["date"] = date_m.group(1).strip()

    # Trending themes table — only rows starting with a digit
    for row in re.findall(
        r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$",
        content,
        re.MULTILINE,
    ):
        rank, theme, fmt, views, example = row
        link_m = re.search(r"\[(.+?)\]\((https?://\S+)\)", example)
        out["themes"].append({
            "rank": rank.strip(),
            "theme": theme.strip(),
            "format": fmt.strip(),
            "views_per_day": views.strip(),
            "example": link_m.group(1) if link_m else example.strip(),
            "example_url": link_m.group(2) if link_m else "",
        })

    # Content ideas
    for block in re.split(r"(?=\n### \d+\.)", "\n" + content):
        if not re.match(r"\n### \d+\.", block):
            continue
        idea: dict = {}
        m = re.search(r"### \d+\. (.+)", block)
        if m:
            idea["title"] = m.group(1).strip()
        for pattern, key in [
            (r"\*\*Label:\*\*\s*(.+)", "label"),
            (r"\*\*Source trend:\*\*\s*(https?://\S+)", "source"),
            (r"\*\*3-second hook:\*\*\s*(.+)", "hook"),
            (r"\*\*Effort:\*\*\s*(\w+)", "effort"),
            (r"\*\*Why it works in India:\*\*\s*(.+)", "why"),
            (r"\*\*Hashtags:\*\*\s*(.+)", "hashtags"),
        ]:
            fm = re.search(pattern, block)
            if fm:
                idea[key] = fm.group(1).strip()
        idea["shots"] = re.findall(r"\d\.\s+\*(.+?)\*:\s*(.+?)(?=\n|$)", block)
        if idea.get("title"):
            out["ideas"].append(idea)

    # Run stats
    stats_m = re.search(r"## Run Stats\n((?:.+\n?)+)", content)
    if stats_m:
        for line in stats_m.group(1).split("\n"):
            sm = re.match(r"[-–]\s*(.+?):\s*(.+)", line)
            if sm:
                out["stats"][sm.group(1).strip()] = sm.group(2).strip()

    return out


# ── Load reports ──────────────────────────────────────────────────────────────

report_files = sorted(
    [f for f in REPORTS_DIR.glob("*.md") if f.name != ".gitkeep"],
    reverse=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 📡 Social Trends Agent")
    st.caption("Meta Ray-Ban · India Content Ideas")
    st.divider()

    if not report_files:
        st.warning("No reports yet.")
        st.code("uv run python main.py")
        st.stop()

    st.metric("Total reports", len(report_files))
    st.metric("Latest", _timestamp_to_label(report_files[0]).split()[0])

    st.divider()
    st.markdown("**Report history**")
    labels = [_timestamp_to_label(f) for f in report_files]
    selected_idx = st.radio(
        "Select report",
        range(len(report_files)),
        format_func=lambda i: labels[i],
        label_visibility="collapsed",
    )

# ── Main ──────────────────────────────────────────────────────────────────────

content = report_files[selected_idx].read_text(encoding="utf-8")
parsed = _parse(content)

# Header
st.markdown(
    f"""
    <div class="report-header">
        <h1>📡 {parsed['title']}</h1>
        <div class="sub">{"Report date: " + parsed['date'] if parsed['date'] else ""}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Stats row ──────────────────────────────────────────────────────────────────

if parsed["stats"]:
    cols = st.columns(len(parsed["stats"]))
    for col, (label, value) in zip(cols, parsed["stats"].items()):
        with col:
            num = re.search(r"\d+", value)
            st.metric(label, num.group() if num else value)

# ── Trending themes ───────────────────────────────────────────────────────────

if parsed["themes"]:
    st.markdown('<div class="section-heading">🔥 Trending Themes</div>', unsafe_allow_html=True)
    for t in parsed["themes"]:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 3, 2])
            with c1:
                st.markdown(f"**#{t['rank']} — {t['theme']}**")
                st.caption(t["format"])
            with c2:
                if t["example_url"]:
                    st.markdown(f"[▶ {t['example'][:60]}{'…' if len(t['example']) > 60 else ''}]({t['example_url']})")
                else:
                    st.caption(t["example"][:80])
            with c3:
                st.metric("Avg views / day", t["views_per_day"])

# ── Content ideas ─────────────────────────────────────────────────────────────

if parsed["ideas"]:
    st.markdown('<div class="section-heading">💡 Content Ideas</div>', unsafe_allow_html=True)
    for i, idea in enumerate(parsed["ideas"], 1):
        label_badge = _badge(idea.get("label", ""), idea.get("label", ""))
        effort_badge = _badge(idea.get("effort", ""), idea.get("effort", ""))
        header = f"**{i}. {idea.get('title', '')}**"
        with st.expander(header, expanded=(i == 1)):
            # Badge row
            st.markdown(
                f"{label_badge} &nbsp; {effort_badge} effort",
                unsafe_allow_html=True,
            )

            # Hook
            if idea.get("hook"):
                st.markdown(
                    f'<div class="hook-box">"{idea["hook"]}"</div>',
                    unsafe_allow_html=True,
                )

            col_left, col_right = st.columns([3, 2])

            with col_left:
                # Shot list
                if idea.get("shots"):
                    st.markdown("**POV Shot List**")
                    for shot_name, shot_desc in idea["shots"]:
                        st.markdown(f"• **{shot_name}** — {shot_desc}")

                # Why it works
                if idea.get("why"):
                    st.markdown("**Why it works in India**")
                    st.markdown(
                        f'<div class="why-box">{idea["why"]}</div>',
                        unsafe_allow_html=True,
                    )

            with col_right:
                # Source
                if idea.get("source"):
                    st.markdown("**Source Trend**")
                    st.markdown(f"[View on YouTube]({idea['source']})")

                # Hashtags
                if idea.get("hashtags"):
                    st.markdown("**Hashtags**")
                    tags = idea["hashtags"].replace(" ", "\n")
                    st.markdown(
                        f'<div class="hashtags">{idea["hashtags"]}</div>',
                        unsafe_allow_html=True,
                    )
