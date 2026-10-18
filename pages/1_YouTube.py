"""YouTube source page — raw data from bronze_youtube."""

import sys
from pathlib import Path
from collections import Counter

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard_utils import inject_ui, load_db, no_data_notice, EMERALD, PLOTLY_LAYOUT

st.set_page_config(page_title="YouTube — Social Trends", page_icon="▶️", layout="wide")
inject_ui()

st.markdown(
    '<div class="source-header source-yt">'
    '<h1>▶️ YouTube</h1>'
    '<div class="sub">Raw videos collected via YouTube Data API v3 · ranked by views / day</div>'
    '</div>',
    unsafe_allow_html=True,
)

conn = load_db()
if conn is None:
    no_data_notice()
    st.stop()

rows = conn.execute(
    "SELECT * FROM bronze_youtube ORDER BY views_per_day DESC"
).fetchdf()
conn.close()

if rows.empty:
    no_data_notice()
    st.stop()

# ── Metrics ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Videos collected", len(rows))
c2.metric("Avg views / day", f"{rows['views_per_day'].mean():,.0f}")
c3.metric("Top channel", rows.iloc[0]["channel"][:22])
c4.metric("Unique channels", rows["channel"].nunique())

st.divider()

# ── Top videos chart ──────────────────────────────────────────────────────────
top = rows.head(15)
labels = [t[:45] + "…" if len(t) > 45 else t for t in top["title"]]
colors = (EMERALD * 3)[: len(top)]

fig_top = go.Figure(go.Bar(
    x=top["views_per_day"].tolist(), y=labels, orientation="h",
    marker=dict(color=colors[::-1], line=dict(color="white", width=1)),
    text=[f"{v:,.0f}" for v in top["views_per_day"]],
    textposition="outside",
    hovertemplate="<b>%{y}</b><br>%{x:,.0f} views/day<extra></extra>",
))
fig_top.update_layout(
    **PLOTLY_LAYOUT,
    title=dict(text="Top 15 Videos by Views / Day", font=dict(size=14, color="#065f46")),
    xaxis=dict(showgrid=True, gridcolor="#d1fae5", zeroline=False, title="Views per day"),
    yaxis=dict(showgrid=False, autorange="reversed"),
    height=420,
)
st.plotly_chart(fig_top, use_container_width=True, key="yt_top_videos")

# ── Channel & query breakdown ─────────────────────────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    ch_counts = rows["channel"].value_counts().head(10)
    fig_ch = go.Figure(go.Bar(
        x=ch_counts.values.tolist(),
        y=ch_counts.index.tolist(),
        orientation="h",
        marker=dict(color=EMERALD[1], opacity=0.85),
        hovertemplate="<b>%{y}</b><br>%{x} videos<extra></extra>",
    ))
    fig_ch.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Top Channels by Video Count", font=dict(size=14, color="#065f46")),
        xaxis=dict(showgrid=True, gridcolor="#d1fae5", title="Videos"),
        yaxis=dict(showgrid=False, autorange="reversed"),
        height=320,
    )
    st.plotly_chart(fig_ch, use_container_width=True, key="yt_channels")

with col_b:
    q_counts = rows["query"].value_counts()
    fig_q = go.Figure(go.Pie(
        labels=q_counts.index.tolist(),
        values=q_counts.values.tolist(),
        marker=dict(colors=EMERALD, line=dict(color="white", width=2)),
        hole=0.5,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value} videos<extra></extra>",
    ))
    fig_q.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Videos per Search Query", font=dict(size=14, color="#065f46")),
        height=320,
        showlegend=False,
    )
    st.plotly_chart(fig_q, use_container_width=True, key="yt_queries")

# ── Full table ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-heading">All Videos</div>', unsafe_allow_html=True)

for _, r in rows.iterrows():
    with st.container(border=True):
        c1, c2, c3 = st.columns([5, 2, 2])
        with c1:
            st.markdown(f"**[{r['title']}]({r['url']})**")
            st.caption(f"{r['channel']} · {r['days_old']} days old")
        with c2:
            st.metric("Views / day", f"{r['views_per_day']:,.0f}")
        with c3:
            st.metric("Total views", f"{int(r['views']):,}")
