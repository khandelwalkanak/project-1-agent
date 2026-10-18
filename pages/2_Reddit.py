"""Reddit source page — raw posts from bronze_reddit."""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard_utils import inject_ui, load_db, no_data_notice, EMERALD, PLOTLY_LAYOUT

st.set_page_config(page_title="Reddit — Social Trends", page_icon="💬", layout="wide")
inject_ui()

st.markdown(
    '<div class="source-header source-rd">'
    '<h1>💬 Reddit</h1>'
    '<div class="sub">Posts collected via Tavily → site:reddit.com targeting · '
    'subreddits: r/RayBanMeta · r/AIGlasses · r/smartglasses · r/wearables · r/gadgets · r/india · r/IndianGaming · r/TechIndia</div>'
    '</div>',
    unsafe_allow_html=True,
)

conn = load_db()
if conn is None:
    no_data_notice()
    st.stop()

rows = conn.execute(
    "SELECT * FROM bronze_reddit ORDER BY fetched_at DESC"
).fetchdf()
conn.close()

if rows.empty:
    no_data_notice()
    st.stop()

# ── Metrics ───────────────────────────────────────────────────────────────────
top_sub = rows["subreddit"].value_counts().idxmax() if not rows["subreddit"].isnull().all() else "—"
c1, c2, c3 = st.columns(3)
c1.metric("Posts collected", len(rows))
c2.metric("Subreddits hit", rows["subreddit"].nunique())
c3.metric("Top subreddit", f"r/{top_sub}")

st.divider()

# ── Posts per subreddit ───────────────────────────────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    sub_counts = rows["subreddit"].value_counts()
    fig_sub = go.Figure(go.Bar(
        x=sub_counts.values.tolist(),
        y=[f"r/{s}" for s in sub_counts.index.tolist()],
        orientation="h",
        marker=dict(
            color=["#f97316"] * len(sub_counts),
            opacity=0.85,
            line=dict(color="white", width=1),
        ),
        hovertemplate="<b>%{y}</b><br>%{x} posts<extra></extra>",
    ))
    fig_sub.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Posts per Subreddit", font=dict(size=14, color="#065f46")),
        xaxis=dict(showgrid=True, gridcolor="#d1fae5", title="Posts"),
        yaxis=dict(showgrid=False, autorange="reversed"),
        height=320,
    )
    st.plotly_chart(fig_sub, use_container_width=True, key="rd_subreddits")

with col_b:
    q_counts = rows["query"].value_counts().head(8)
    fig_q = go.Figure(go.Bar(
        x=q_counts.values.tolist(),
        y=q_counts.index.tolist(),
        orientation="h",
        marker=dict(color="#fb923c", opacity=0.85, line=dict(color="white", width=1)),
        hovertemplate="<b>%{y}</b><br>%{x} posts<extra></extra>",
    ))
    fig_q.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Posts per Search Query", font=dict(size=14, color="#065f46")),
        xaxis=dict(showgrid=True, gridcolor="#d1fae5", title="Posts"),
        yaxis=dict(showgrid=False, autorange="reversed"),
        height=320,
    )
    st.plotly_chart(fig_q, use_container_width=True, key="rd_queries")

# ── Posts table ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-heading">All Posts</div>', unsafe_allow_html=True)

for _, r in rows.iterrows():
    with st.container(border=True):
        c1, c2 = st.columns([7, 2])
        with c1:
            sub_label = f"r/{r['subreddit']}" if r["subreddit"] else "Reddit"
            st.markdown(f"**[{r['title']}]({r['url']})**")
            st.caption(sub_label)
            if r.get("selftext"):
                st.markdown(
                    f'<div class="why-box">{str(r["selftext"])[:280]}…</div>',
                    unsafe_allow_html=True,
                )
        with c2:
            st.caption("Search query")
            st.markdown(f"`{str(r['query'])[:40]}`")
