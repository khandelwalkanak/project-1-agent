"""
Streamlit dashboard — social trends reports viewer.

Run locally:   uv run --extra dashboard streamlit run dashboard.py
Deploy:        https://share.streamlit.io
"""

import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Social Trends Agent",
    page_icon="📡",
    layout="wide",
)

REPORTS_DIR = Path("reports")

# ── Cursor-tracking gradient (JS → CSS variable) ──────────────────────────────
components.html("""
<script>
(function () {
    function init() {
        var root = window.parent.document.documentElement;
        if (!root) { setTimeout(init, 300); return; }
        window.parent.addEventListener('mousemove', function (e) {
            root.style.setProperty('--cx', (e.clientX / window.parent.innerWidth  * 100).toFixed(1) + '%');
            root.style.setProperty('--cy', (e.clientY / window.parent.innerHeight * 100).toFixed(1) + '%');
        });
    }
    init();
})();
</script>
""", height=0)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root { --cx: 50%; --cy: 30%; }

/* Cursor-driven radial gradient — layered on top of the config.toml white base */
[data-testid="stAppViewContainer"] {
    background: radial-gradient(
        ellipse 70% 55% at var(--cx) var(--cy),
        #d1fae5 0%, #ecfdf5 20%, #ffffff 55%
    ) !important;
}

/* Metric cards */
div[data-testid="metric-container"] {
    background: rgba(240, 253, 244, 0.85);
    border: 1px solid #6ee7b7;
    border-radius: 12px;
    padding: 18px 20px !important;
}

/* Badges */
.badge {
    display: inline-block; padding: 3px 12px; border-radius: 20px;
    font-size: 0.76em; font-weight: 700; letter-spacing: 0.4px; text-transform: uppercase;
}
.badge-SAME       { background: #dbeafe; color: #1d4ed8; }
.badge-TWIST      { background: #fed7aa; color: #c2410c; }
.badge-WHITESPACE { background: #a7f3d0; color: #047857; }
.badge-low        { background: #d1fae5; color: #065f46; }
.badge-med        { background: #fef9c3; color: #92400e; }
.badge-high       { background: #fecaca; color: #b91c1c; }

/* 3-second hook callout */
.hook-box {
    background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
    border-left: 4px solid #10b981;
    padding: 12px 18px; border-radius: 0 10px 10px 0;
    font-style: italic; color: #065f46;
    margin: 10px 0 14px 0; line-height: 1.6; font-size: 0.95em;
}

/* Why it works */
.why-box {
    background: #f9fafb; border: 1px solid #d1fae5; border-radius: 8px;
    padding: 10px 16px; color: #374151; font-size: 0.88em; line-height: 1.6; margin-top: 6px;
}

/* Hashtags */
.hashtags { color: #059669; font-size: 0.82em; line-height: 1.8; }

/* Section headings */
.section-heading {
    font-size: 1.05em; font-weight: 700; color: #064e3b;
    margin: 24px 0 12px 0; padding-bottom: 8px;
    border-bottom: 2px solid #6ee7b7; letter-spacing: 0.3px;
}

/* Report header */
.report-header {
    background: linear-gradient(135deg, #065f46 0%, #059669 60%, #10b981 100%);
    border-radius: 14px; padding: 26px 32px; margin-bottom: 20px; color: white;
    box-shadow: 0 4px 24px rgba(5, 150, 105, 0.18);
}
.report-header h1 { margin: 0 0 6px 0; font-size: 1.65em; font-weight: 800; color: white; }
.report-header .sub { color: #a7f3d0; font-size: 0.88em; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

_EMERALD = ["#065f46", "#059669", "#10b981", "#34d399", "#6ee7b7", "#a7f3d0"]
_LABEL_COLORS  = {"SAME": "#3b82f6", "TWIST": "#f97316", "WHITESPACE": "#10b981"}
_EFFORT_COLORS = {"low": "#10b981", "med": "#f59e0b", "high": "#ef4444"}

_PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, -apple-system, sans-serif", color="#111827"),
    margin=dict(l=16, r=16, t=36, b=16),
    hoverlabel=dict(bgcolor="white", bordercolor="#6ee7b7", font_color="#111827"),
)


def _timestamp_to_label(path: Path) -> str:
    m = re.search(r"(\d{9,10})", path.stem)
    if m:
        try:
            return datetime.fromtimestamp(int(m.group(1))).strftime("%b %d, %Y  %H:%M")
        except Exception:
            pass
    return path.stem


def _parse_num(s: str) -> int:
    m = re.search(r"[\d,]+", str(s))
    return int(m.group().replace(",", "")) if m else 0


def _badge(text: str) -> str:
    key = text.strip().upper().replace(" ", "")
    return f'<span class="badge badge-{key}">{text.strip()}</span>'


def _parse(content: str) -> dict:
    out = {"title": "Meta Smart Glasses — India Content Ideas", "date": "", "themes": [], "ideas": [], "stats": {}}

    m = re.search(r"^# (.+)$", content, re.MULTILINE)
    if m: out["title"] = m.group(1).strip()

    m = re.search(r"_Report date:\s*(.+?)_", content)
    if m: out["date"] = m.group(1).strip()

    for row in re.findall(
        r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$",
        content, re.MULTILINE,
    ):
        rank, theme, fmt, views, example = row
        lm = re.search(r"\[(.+?)\]\((https?://\S+)\)", example)
        out["themes"].append({
            "rank": rank.strip(), "theme": theme.strip(),
            "format": fmt.strip(), "views_per_day": views.strip(),
            "views_num": _parse_num(views),
            "example": lm.group(1) if lm else example.strip(),
            "example_url": lm.group(2) if lm else "",
        })

    for block in re.split(r"(?=\n### \d+\.)", "\n" + content):
        if not re.match(r"\n### \d+\.", block):
            continue
        idea: dict = {}
        m = re.search(r"### \d+\. (.+)", block)
        if m: idea["title"] = m.group(1).strip()
        for pattern, key in [
            (r"\*\*Label:\*\*\s*(.+)",         "label"),
            (r"\*\*Source trend:\*\*\s*(https?://\S+)", "source"),
            (r"\*\*3-second hook:\*\*\s*(.+)", "hook"),
            (r"\*\*Effort:\*\*\s*(\w+)",       "effort"),
            (r"\*\*Why it works in India:\*\*\s*(.+)", "why"),
            (r"\*\*Hashtags:\*\*\s*(.+)",      "hashtags"),
        ]:
            fm = re.search(pattern, block)
            if fm: idea[key] = fm.group(1).strip()
        idea["shots"] = re.findall(r"\d\.\s+\*(.+?)\*:\s*(.+?)(?=\n|$)", block)
        if idea.get("title"):
            out["ideas"].append(idea)

    sm = re.search(r"## Run Stats\n((?:.+\n?)+)", content)
    if sm:
        for line in sm.group(1).split("\n"):
            lm = re.match(r"[-–]\s*(.+?):\s*(.+)", line)
            if lm: out["stats"][lm.group(1).strip()] = lm.group(2).strip()

    return out


# ── Charts ────────────────────────────────────────────────────────────────────

def _chart_themes(themes: list[dict]) -> go.Figure:
    sorted_t = sorted(themes, key=lambda t: t["views_num"])
    labels = [t["theme"][:35] + "…" if len(t["theme"]) > 35 else t["theme"] for t in sorted_t]
    values = [t["views_num"] for t in sorted_t]
    colors = _EMERALD[: len(sorted_t)][::-1]

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=colors, line=dict(color="white", width=1)),
        text=[f"{v:,}" for v in values],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x:,} views/day<extra></extra>",
    ))
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title=dict(text="Avg Views / Day by Theme", font=dict(size=14, color="#065f46")),
        xaxis=dict(showgrid=True, gridcolor="#d1fae5", zeroline=False, title="Views per day"),
        yaxis=dict(showgrid=False),
        height=280,
    )
    return fig


def _chart_labels(ideas: list[dict]) -> go.Figure:
    counts = Counter(i.get("label", "Unknown").strip().upper() for i in ideas)
    labels, values = zip(*counts.items()) if counts else ([], [])
    colors = [_LABEL_COLORS.get(l, "#94a3b8") for l in labels]

    fig = go.Figure(go.Pie(
        labels=list(labels), values=list(values),
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        hole=0.55,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value} ideas (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title=dict(text="Idea Type Mix", font=dict(size=14, color="#065f46")),
        height=260,
        showlegend=False,
    )
    return fig


def _chart_effort(ideas: list[dict]) -> go.Figure:
    counts = Counter(i.get("effort", "?").strip().lower() for i in ideas)
    order = ["low", "med", "high"]
    labels = [l for l in order if l in counts]
    values = [counts[l] for l in labels]
    colors = [_EFFORT_COLORS[l] for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        hole=0.55,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value} ideas<extra></extra>",
    ))
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title=dict(text="Effort Distribution", font=dict(size=14, color="#065f46")),
        height=260,
        showlegend=False,
    )
    return fig


def _chart_trends(report_files: list[Path]) -> go.Figure:
    dates, yt_counts, web_counts = [], [], []
    for f in sorted(report_files):
        content = f.read_text(encoding="utf-8")
        m = re.search(r"(\d{9,10})", f.stem)
        if not m:
            continue
        dt = datetime.fromtimestamp(int(m.group(1)))
        yt_m  = re.search(r"YouTube videos collected:\s*(\d+)", content)
        web_m = re.search(r"Web results collected:\s*(\d+)", content)
        dates.append(dt)
        yt_counts.append(int(yt_m.group(1)) if yt_m else 0)
        web_counts.append(int(web_m.group(1)) if web_m else 0)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=yt_counts, name="YouTube videos",
        mode="lines+markers",
        line=dict(color="#059669", width=2.5),
        marker=dict(size=8, color="#059669"),
        hovertemplate="%{x|%b %d %H:%M}<br><b>%{y} videos</b><extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=web_counts, name="Web results",
        mode="lines+markers",
        line=dict(color="#6ee7b7", width=2, dash="dot"),
        marker=dict(size=6, color="#6ee7b7"),
        hovertemplate="%{x|%b %d %H:%M}<br><b>%{y} web results</b><extra></extra>",
    ))
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title=dict(text="Data Collected Per Run", font=dict(size=14, color="#065f46")),
        xaxis=dict(showgrid=True, gridcolor="#d1fae5", title="Run date"),
        yaxis=dict(showgrid=True, gridcolor="#d1fae5", title="Count"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=320,
    )
    return fig


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
    st.metric("Latest run", _timestamp_to_label(report_files[0]).split()[0])
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
parsed  = _parse(content)

# Header
st.markdown(
    f"""<div class="report-header">
        <h1>📡 {parsed['title']}</h1>
        <div class="sub">{"Report date: " + parsed['date'] if parsed['date'] else "No date"}</div>
    </div>""",
    unsafe_allow_html=True,
)

# Stats row
if parsed["stats"]:
    cols = st.columns(len(parsed["stats"]))
    for col, (label, value) in zip(cols, parsed["stats"].items()):
        with col:
            n = re.search(r"\d+", value)
            st.metric(label, n.group() if n else value)

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_overview, tab_themes, tab_ideas, tab_trends = st.tabs(
    ["📊 Overview", "🔥 Trending Themes", "💡 Content Ideas", "📈 Trends"]
)

# ── Overview tab ──────────────────────────────────────────────────────────────

with tab_overview:
    if parsed["themes"]:
        st.plotly_chart(_chart_themes(parsed["themes"]), use_container_width=True, key="overview_themes")

    if parsed["ideas"]:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(_chart_labels(parsed["ideas"]), use_container_width=True, key="overview_labels")
        with c2:
            st.plotly_chart(_chart_effort(parsed["ideas"]), use_container_width=True, key="overview_effort")

        # Quick summary table
        st.markdown('<div class="section-heading">Ideas at a Glance</div>', unsafe_allow_html=True)
        for idea in parsed["ideas"]:
            c_title, c_label, c_effort = st.columns([5, 2, 2])
            with c_title: st.markdown(f"**{idea['title']}**")
            with c_label:
                st.markdown(_badge(idea.get("label", "—")), unsafe_allow_html=True)
            with c_effort:
                st.markdown(_badge(idea.get("effort", "—")), unsafe_allow_html=True)

# ── Themes tab ────────────────────────────────────────────────────────────────

with tab_themes:
    if parsed["themes"]:
        st.plotly_chart(_chart_themes(parsed["themes"]), use_container_width=True, key="themes_bar")
        st.markdown('<div class="section-heading">Theme Breakdown</div>', unsafe_allow_html=True)
        for t in parsed["themes"]:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 3, 2])
                with c1:
                    st.markdown(f"**#{t['rank']} — {t['theme']}**")
                    st.caption(t["format"])
                with c2:
                    if t["example_url"]:
                        st.markdown(f"[▶ {t['example'][:55]}{'…' if len(t['example']) > 55 else ''}]({t['example_url']})")
                    else:
                        st.caption(t["example"][:80])
                with c3:
                    st.metric("Avg views / day", t["views_per_day"])

# ── Ideas tab ─────────────────────────────────────────────────────────────────

with tab_ideas:
    if parsed["ideas"]:
        for i, idea in enumerate(parsed["ideas"], 1):
            with st.expander(f"**{i}. {idea.get('title', '')}**", expanded=(i == 1)):
                st.markdown(
                    f"{_badge(idea.get('label', ''))} &nbsp; {_badge(idea.get('effort', ''))} effort",
                    unsafe_allow_html=True,
                )
                if idea.get("hook"):
                    st.markdown(
                        f'<div class="hook-box">"{idea["hook"]}"</div>',
                        unsafe_allow_html=True,
                    )
                col_left, col_right = st.columns([3, 2])
                with col_left:
                    if idea.get("shots"):
                        st.markdown("**POV Shot List**")
                        for shot_name, shot_desc in idea["shots"]:
                            st.markdown(f"• **{shot_name}** — {shot_desc}")
                    if idea.get("why"):
                        st.markdown("**Why it works in India**")
                        st.markdown(
                            f'<div class="why-box">{idea["why"]}</div>',
                            unsafe_allow_html=True,
                        )
                with col_right:
                    if idea.get("source"):
                        st.markdown("**Source Trend**")
                        st.markdown(f"[▶ View on YouTube]({idea['source']})")
                    if idea.get("hashtags"):
                        st.markdown("**Hashtags**")
                        st.markdown(
                            f'<div class="hashtags">{idea["hashtags"]}</div>',
                            unsafe_allow_html=True,
                        )

# ── Trends tab ────────────────────────────────────────────────────────────────

with tab_trends:
    if len(report_files) >= 2:
        st.plotly_chart(_chart_trends(report_files), use_container_width=True, key="trends_line")
    else:
        st.info("Run the agent at least twice to see trends across reports.")
        st.caption("The chart will show YouTube videos and web results collected per run over time.")
