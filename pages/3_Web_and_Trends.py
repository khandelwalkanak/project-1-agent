"""Web search + Google Trends source page — article cards."""

import sys
from urllib.parse import urlparse
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard_utils import inject_ui, load_db, no_data_notice, PLOTLY_LAYOUT

st.set_page_config(page_title="Web & Trends — Social Trends", page_icon="https://www.google.com/s2/favicons?domain=google.com&sz=32", layout="wide")
inject_ui()

st.markdown("""
<style>
.web-card {
    background: white; border-radius: 12px; padding: 16px 20px;
    border: 1px solid #e5e7eb; margin-bottom: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    transition: box-shadow .2s, border-color .2s;
}
.web-card:hover { box-shadow: 0 4px 16px rgba(59,130,246,0.15); border-color: #93c5fd; }
.web-domain {
    display: inline-flex; align-items: center; gap: 6px;
    background: #eff6ff; color: #1d4ed8; border-radius: 20px;
    padding: 2px 10px; font-size: 0.74em; font-weight: 700;
    margin-bottom: 8px; text-transform: lowercase;
}
.web-domain img { width: 14px; height: 14px; border-radius: 2px; }
.web-title { font-size: 0.97em; font-weight: 700; color: #111827;
             text-decoration: none; line-height: 1.45; }
.web-title:hover { color: #1d4ed8; }
.web-snippet { color: #4b5563; font-size: 0.84em; line-height: 1.6;
               margin: 8px 0 10px 0; border-left: 3px solid #93c5fd;
               padding-left: 10px; }
.web-meta { font-size: 0.76em; color: #9ca3af; }
.query-tag {
    display: inline-block; background: #f0fdf4; color: #065f46;
    border: 1px solid #6ee7b7; border-radius: 20px; padding: 2px 10px;
    font-size: 0.74em; font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="source-header source-web">'
    '<div style="display:flex;align-items:center;gap:18px;">'
    '<img src="https://upload.wikimedia.org/wikipedia/commons/2/2f/Google_2015_logo.svg" '
    'style="height:32px;background:white;border-radius:8px;padding:6px 12px;" />'
    '<div>'
    '<h1 style="margin:0 0 4px 0;">Web & Google Trends</h1>'
    '<div class="sub">Articles, blogs, and discussions via Tavily web search · '
    'Google Trends interest scores for India</div>'
    '</div></div></div>',
    unsafe_allow_html=True,
)


def _render_web_card(r) -> None:
    domain = urlparse(str(r["url"])).netloc.replace("www.", "")
    favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=16"
    snippet = str(r.get("snippet") or "").strip()
    date = str(r.get("published_date") or "")[:10]
    query = str(r.get("query") or "")[:50]

    st.markdown(
        f'<div class="web-card">'
        f'<div class="web-domain"><img src="{favicon}" />{domain}</div>'
        f'<a class="web-title" href="{r["url"]}" target="_blank">{r["title"]}</a>'
        + (f'<div class="web-snippet">{snippet[:350]}{"…" if len(snippet) > 350 else ""}</div>' if snippet else "")
        + f'<div class="web-meta">'
        + (f'📅 {date} &nbsp;·&nbsp; ' if date else "")
        + f'🔍 <code>{query}</code>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


# ── Load data ─────────────────────────────────────────────────────────────────
conn = load_db()
if conn is None:
    no_data_notice()
    st.stop()

web_rows = conn.execute("SELECT * FROM bronze_web ORDER BY fetched_at DESC").fetchdf()
conn.close()

# ── Web results section ───────────────────────────────────────────────────────
st.markdown('<div class="section-heading">🔍 Web Articles & Discussions</div>', unsafe_allow_html=True)

if web_rows.empty:
    no_data_notice()
else:
    c1, c2, c3 = st.columns(3)
    c1.metric("Articles collected", len(web_rows))
    c2.metric("Search queries", web_rows["query"].nunique())
    c3.metric("Unique domains", web_rows["url"].apply(lambda u: urlparse(u).netloc).nunique())

    st.divider()

    # ── Trends summary ────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">📊 Trends Summary</div>', unsafe_allow_html=True)

    _q_counts   = web_rows["query"].value_counts()
    _domains    = web_rows["url"].apply(lambda u: urlparse(u).netloc.replace("www.", ""))
    _dom_counts = _domains.value_counts()
    _top_q      = _q_counts.index[0]
    _top_dom    = _dom_counts.index[0]
    _sec_dom    = _dom_counts.index[1] if len(_dom_counts) > 1 else None

    _para = (
        f"{len(web_rows)} articles were collected from {_domains.nunique()} unique domains "
        f"across {web_rows['query'].nunique()} search queries. "
        f"The most covered topic was <b>{_top_q}</b> with {_q_counts.iloc[0]} articles. "
        f"<b>{_top_dom}</b> was the most cited source with {_dom_counts.iloc[0]} articles"
        + (f", followed by <b>{_sec_dom}</b> with {_dom_counts.iloc[1]} articles" if _sec_dom else "")
        + "."
    )
    st.markdown(
        f'<div class="trends-paragraph" style="border-left-color:#3b82f6;'
        f'background:linear-gradient(135deg,#eff6ff 0%,#f9fafb 100%);">{_para}</div>',
        unsafe_allow_html=True,
    )

    _q_tbl = _q_counts.reset_index()
    _q_tbl.columns = ["Search Query", "Articles"]
    _q_tbl["Share"] = (_q_tbl["Articles"] / _q_tbl["Articles"].sum() * 100).round(1)

    _dom_tbl = _dom_counts.head(10).reset_index()
    _dom_tbl.columns = ["Domain", "Articles"]
    _dom_tbl["Favicon"] = (
        "https://www.google.com/s2/favicons?domain=" + _dom_tbl["Domain"] + "&sz=32"
    )
    _dom_tbl["Share"] = (_dom_tbl["Articles"] / _dom_tbl["Articles"].sum() * 100).round(1)

    _tc1, _tc2 = st.columns(2)
    with _tc1:
        st.caption("By search query")
        st.dataframe(
            _q_tbl,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Search Query": st.column_config.TextColumn("Search Query", width="large"),
                "Articles": st.column_config.NumberColumn("Articles", format="%d"),
                "Share": st.column_config.ProgressColumn(
                    "Share %", format="%.0f%%", min_value=0, max_value=100,
                ),
            },
        )
    with _tc2:
        st.caption("By source domain")
        st.dataframe(
            _dom_tbl[["Favicon", "Domain", "Articles", "Share"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Favicon": st.column_config.ImageColumn(" ", width="small"),
                "Domain": st.column_config.TextColumn("Domain"),
                "Articles": st.column_config.NumberColumn("Articles", format="%d"),
                "Share": st.column_config.ProgressColumn(
                    "Share %", format="%.0f%%", min_value=0, max_value=100,
                ),
            },
        )

    st.divider()

    with st.sidebar:
        st.markdown("### 🌐 Filters")
        queries = ["All"] + sorted(web_rows["query"].unique().tolist())
        sel_query = st.selectbox("Search query", queries)

    df = web_rows.copy()
    if sel_query != "All":
        df = df[df["query"] == sel_query]
    df = df.reset_index(drop=True)

    st.caption(f"Showing {len(df)} of {len(web_rows)} articles")

    if sel_query == "All":
        for query, group in df.groupby("query"):
            st.markdown(
                f'<div class="section-heading">'
                f'<span class="query-tag">🔍 {query}</span>'
                f' &nbsp; {len(group)} results'
                f'</div>',
                unsafe_allow_html=True,
            )
            for _, r in group.iterrows():
                _render_web_card(r)
    else:
        for _, r in df.iterrows():
            _render_web_card(r)

    with st.expander("📊 Domain Breakdown"):
        domains = web_rows["url"].apply(lambda u: urlparse(u).netloc.replace("www.", ""))
        dc = domains.value_counts().head(15)
        fig = go.Figure(go.Bar(
            x=dc.values.tolist(), y=dc.index.tolist(), orientation="h",
            marker=dict(color="#3b82f6", opacity=0.8, line=dict(color="white", width=1)),
            hovertemplate="<b>%{y}</b><br>%{x} articles<extra></extra>",
        ))
        fig.update_layout(**PLOTLY_LAYOUT,
            title=dict(text="Articles per Domain", font=dict(size=13, color="#065f46")),
            xaxis=dict(showgrid=True, gridcolor="#dbeafe"),
            yaxis=dict(autorange="reversed"), height=320)
        st.plotly_chart(fig, use_container_width=True, key="web_domains")

# ── Google Trends note ────────────────────────────────────────────────────────
st.divider()
st.markdown('<div class="section-heading">📈 Google Trends (India)</div>', unsafe_allow_html=True)
st.info(
    "Google Trends validates whether themes are **rising, stable, or falling** in India "
    "before the AI commits to a content idea. "
    "The interest scores (0–100) are fed directly to the AI during analysis — "
    "not stored in the database, but reflected in how themes are ranked in the report.",
    icon="ℹ️",
)
