"""Web search + Google Trends source page."""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard_utils import inject_ui, load_db, no_data_notice, PLOTLY_LAYOUT

st.set_page_config(page_title="Web & Trends — Social Trends", page_icon="🌐", layout="wide")
inject_ui()

st.markdown(
    '<div class="source-header source-web">'
    '<h1>🌐 Web & Google Trends</h1>'
    '<div class="sub">Web results via Tavily · Google Trends interest scores for India</div>'
    '</div>',
    unsafe_allow_html=True,
)

conn = load_db()
if conn is None:
    no_data_notice()
    st.stop()

web_rows = conn.execute(
    "SELECT * FROM bronze_web ORDER BY fetched_at DESC"
).fetchdf()
conn.close()

# ── Web results section ───────────────────────────────────────────────────────
st.markdown('<div class="section-heading">🔍 Web Search Results (Tavily)</div>', unsafe_allow_html=True)

if web_rows.empty:
    no_data_notice()
else:
    c1, c2 = st.columns(2)
    c1.metric("Articles collected", len(web_rows))
    c2.metric("Search queries run", web_rows["query"].nunique())

    st.divider()

    # Results per query chart
    q_counts = web_rows["query"].value_counts()
    fig_q = go.Figure(go.Bar(
        x=q_counts.values.tolist(),
        y=q_counts.index.tolist(),
        orientation="h",
        marker=dict(color="#3b82f6", opacity=0.85, line=dict(color="white", width=1)),
        hovertemplate="<b>%{y}</b><br>%{x} results<extra></extra>",
    ))
    fig_q.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Results per Search Query", font=dict(size=14, color="#065f46")),
        xaxis=dict(showgrid=True, gridcolor="#d1fae5", title="Results"),
        yaxis=dict(showgrid=False, autorange="reversed"),
        height=max(200, len(q_counts) * 44),
    )
    st.plotly_chart(fig_q, use_container_width=True, key="web_queries")

    st.markdown('<div class="section-heading">All Web Results</div>', unsafe_allow_html=True)
    for _, r in web_rows.iterrows():
        with st.container(border=True):
            c1, c2 = st.columns([7, 2])
            with c1:
                st.markdown(f"**[{r['title']}]({r['url']})**")
                if r.get("snippet"):
                    st.markdown(
                        f'<div class="why-box">{str(r["snippet"])[:320]}</div>',
                        unsafe_allow_html=True,
                    )
            with c2:
                if r.get("published_date"):
                    st.caption(str(r["published_date"])[:10])
                st.markdown(f"`{str(r['query'])[:35]}`")

# ── Google Trends note ────────────────────────────────────────────────────────
st.divider()
st.markdown('<div class="section-heading">📈 Google Trends</div>', unsafe_allow_html=True)
st.info(
    "Google Trends results are used by the AI during report generation to validate that "
    "themes are rising in India. The raw interest scores are returned to the AI but not "
    "stored in the database. Trend signals appear in the report's theme rankings.",
    icon="ℹ️",
)
