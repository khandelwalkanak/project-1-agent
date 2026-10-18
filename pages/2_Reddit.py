"""Reddit source page — post cards grouped by subreddit."""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard_utils import inject_ui, load_db, no_data_notice, PLOTLY_LAYOUT

st.set_page_config(page_title="Reddit — Social Trends", page_icon="https://www.google.com/s2/favicons?domain=reddit.com&sz=32", layout="wide")
inject_ui()

st.markdown("""
<style>
.rd-card {
    background: white; border-radius: 12px; padding: 16px 18px;
    border: 1px solid #e5e7eb; margin-bottom: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    transition: box-shadow .2s, border-color .2s;
}
.rd-card:hover { box-shadow: 0 4px 16px rgba(249,115,22,0.15); border-color: #fdba74; }
.rd-sub {
    display: inline-block; border-radius: 20px; padding: 2px 12px;
    font-size: 0.74em; font-weight: 700; margin-bottom: 8px;
    text-transform: uppercase; letter-spacing: 0.4px;
}
.rd-title { font-size: 0.97em; font-weight: 700; color: #111827;
            text-decoration: none; line-height: 1.45; }
.rd-title:hover { color: #ea580c; }
.rd-snippet { color: #4b5563; font-size: 0.84em; line-height: 1.6;
              margin: 8px 0 10px 0; border-left: 3px solid #fed7aa;
              padding-left: 10px; }
.rd-meta { font-size: 0.76em; color: #9ca3af; }
.sub-RayBanMeta  { background: #fee2e2; color: #991b1b; }
.sub-AIGlasses   { background: #fef3c7; color: #92400e; }
.sub-smartglasses{ background: #ede9fe; color: #5b21b6; }
.sub-wearables   { background: #dbeafe; color: #1e40af; }
.sub-gadgets     { background: #d1fae5; color: #065f46; }
.sub-india       { background: #fff7ed; color: #9a3412; }
.sub-IndianGaming{ background: #fce7f3; color: #9d174d; }
.sub-TechIndia   { background: #ecfdf5; color: #047857; }
.sub-other       { background: #f3f4f6; color: #374151; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="source-header source-rd">'
    '<div style="display:flex;align-items:center;gap:18px;">'
    '<img src="https://www.redditstatic.com/desktop2x/img/snoovatars/snoo.png" '
    'style="height:52px;width:52px;object-fit:contain;" />'
    '<div>'
    '<h1 style="margin:0 0 4px 0;">Reddit</h1>'
    '<div class="sub">Posts from r/RayBanMeta · r/AIGlasses · r/smartglasses · r/wearables · '
    'r/gadgets · r/india · r/IndianGaming · r/TechIndia — sourced via Tavily</div>'
    '</div></div></div>',
    unsafe_allow_html=True,
)

conn = load_db()
if conn is None:
    no_data_notice()
    st.stop()

rows = conn.execute("SELECT * FROM bronze_reddit ORDER BY fetched_at DESC").fetchdf()
conn.close()

if rows.empty:
    no_data_notice()
    st.stop()

# ── Metrics ───────────────────────────────────────────────────────────────────
top_sub = rows["subreddit"].value_counts().idxmax() if not rows["subreddit"].isnull().all() else "—"
c1, c2, c3 = st.columns(3)
c1.metric("Posts collected", len(rows))
c2.metric("Subreddits covered", rows["subreddit"].nunique())
c3.metric("Most active", f"r/{top_sub}")

st.divider()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💬 Filters")
    all_subs = ["All"] + sorted(rows["subreddit"].dropna().unique().tolist())
    sel_sub = st.selectbox("Subreddit", all_subs)
    all_queries = ["All"] + sorted(rows["query"].unique().tolist())
    sel_query = st.selectbox("Search query", all_queries)

df = rows.copy()
if sel_sub != "All":
    df = df[df["subreddit"] == sel_sub]
if sel_query != "All":
    df = df[df["query"] == sel_query]
df = df.reset_index(drop=True)

st.caption(f"Showing {len(df)} of {len(rows)} posts")


_SUB_CANONICAL = {s.lower(): s for s in
    ["RayBanMeta", "AIGlasses", "smartglasses", "wearables", "gadgets", "india", "IndianGaming", "TechIndia"]}

def _sub_class(sub: str) -> str:
    canonical = _SUB_CANONICAL.get(sub.lower())
    return f"sub-{canonical}" if canonical else "sub-other"


# ── Posts grouped by subreddit ────────────────────────────────────────────────
if sel_sub == "All":
    sub_order = df["subreddit"].value_counts().index.tolist()
    for sub in sub_order:
        sub_df = df[df["subreddit"] == sub]
        display_sub = _SUB_CANONICAL.get(sub.lower(), sub)
        st.markdown(
            f'<div class="section-heading">'
            f'<span class="rd-sub {_sub_class(sub)}">r/{display_sub}</span>'
            f' &nbsp; {len(sub_df)} posts'
            f'</div>',
            unsafe_allow_html=True,
        )
        for _, r in sub_df.iterrows():
            snippet = str(r.get("selftext") or "").strip()
            query_label = str(r.get("query") or "")[:45]
            st.markdown(
                f'<div class="rd-card">'
                f'<a class="rd-title" href="{r["url"]}" target="_blank">{r["title"]}</a>'
                + (f'<div class="rd-snippet">{snippet[:300]}{"…" if len(snippet) > 300 else ""}</div>' if snippet else "")
                + f'<div class="rd-meta">🔍 query: <code>{query_label}</code></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
else:
    for _, r in df.iterrows():
        sub = str(r.get("subreddit") or "")
        snippet = str(r.get("selftext") or "").strip()
        query_label = str(r.get("query") or "")[:45]
        st.markdown(
            f'<div class="rd-card">'
            f'<span class="rd-sub {_sub_class(sub)}">r/{sub}</span><br/>'
            f'<a class="rd-title" href="{r["url"]}" target="_blank">{r["title"]}</a>'
            + (f'<div class="rd-snippet">{snippet[:300]}{"…" if len(snippet) > 300 else ""}</div>' if snippet else "")
            + f'<div class="rd-meta">🔍 query: <code>{query_label}</code></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ── Chart (collapsible) ───────────────────────────────────────────────────────
with st.expander("📊 Subreddit Breakdown"):
    sc = rows["subreddit"].value_counts()
    sub_colors = {
        "RayBanMeta": "#ef4444", "AIGlasses": "#f59e0b", "smartglasses": "#8b5cf6",
        "wearables": "#3b82f6", "gadgets": "#10b981", "india": "#f97316",
        "IndianGaming": "#ec4899", "TechIndia": "#059669",
    }
    bar_colors = [sub_colors.get(s, "#94a3b8") for s in sc.index]
    fig = go.Figure(go.Bar(
        x=sc.values.tolist(), y=[f"r/{s}" for s in sc.index.tolist()],
        orientation="h",
        marker=dict(color=bar_colors, line=dict(color="white", width=1)),
        hovertemplate="<b>%{y}</b><br>%{x} posts<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_LAYOUT,
        title=dict(text="Posts per Subreddit", font=dict(size=13, color="#065f46")),
        xaxis=dict(showgrid=True, gridcolor="#d1fae5"),
        yaxis=dict(autorange="reversed"), height=300)
    st.plotly_chart(fig, use_container_width=True, key="rd_sub_chart")
