"""YouTube source page — video cards with thumbnails."""

import re
import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard_utils import inject_ui, load_db, no_data_notice, EMERALD, PLOTLY_LAYOUT

st.set_page_config(page_title="YouTube — Social Trends", page_icon="https://www.google.com/s2/favicons?domain=youtube.com&sz=32", layout="wide")
inject_ui()

st.markdown("""
<style>
.yt-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 12px 0 24px 0; }
.yt-card {
    background: white; border-radius: 12px; overflow: hidden;
    border: 1px solid #e5e7eb; transition: box-shadow .2s;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.yt-card:hover { box-shadow: 0 4px 18px rgba(5,150,105,0.18); border-color: #6ee7b7; }
.yt-thumb { width: 100%; aspect-ratio: 16/9; object-fit: cover; display: block; }
.yt-body  { padding: 12px 14px 14px 14px; }
.yt-title { font-weight: 700; font-size: 0.88em; color: #111827; line-height: 1.4;
            text-decoration: none; display: block; margin-bottom: 4px; }
.yt-title:hover { color: #059669; }
.yt-channel { font-size: 0.78em; color: #6b7280; margin-bottom: 8px; }
.yt-stats { display: flex; gap: 10px; flex-wrap: wrap; }
.yt-vpd {
    background: #d1fae5; color: #065f46; border-radius: 20px;
    padding: 2px 10px; font-size: 0.75em; font-weight: 700;
}
.yt-age {
    background: #f3f4f6; color: #6b7280; border-radius: 20px;
    padding: 2px 10px; font-size: 0.75em;
}
.yt-views { color: #374151; font-size: 0.75em; padding: 2px 0; }
.rank-badge {
    display: inline-block; background: #065f46; color: white;
    border-radius: 50%; width: 22px; height: 22px; text-align: center;
    line-height: 22px; font-size: 0.72em; font-weight: 800; margin-right: 6px;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="source-header source-yt">'
    '<div style="display:flex;align-items:center;gap:18px;">'
    '<img src="https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" '
    'style="height:36px;background:white;border-radius:8px;padding:6px 10px;" />'
    '<div>'
    '<h1 style="margin:0 0 4px 0;">YouTube</h1>'
    '<div class="sub">Videos collected via YouTube Data API v3 · ranked by views per day (engagement velocity)</div>'
    '</div></div></div>',
    unsafe_allow_html=True,
)

conn = load_db()
if conn is None:
    no_data_notice()
    st.stop()

rows = conn.execute("SELECT * FROM bronze_youtube ORDER BY views_per_day DESC").fetchdf()
conn.close()

if rows.empty:
    no_data_notice()
    st.stop()

# ── Metrics ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Videos collected", len(rows))
c2.metric("Peak views / day", f"{rows['views_per_day'].max():,.0f}")
c3.metric("Unique channels", rows["channel"].nunique())
c4.metric("Avg video age", f"{rows['days_old'].mean():.0f} days")

st.divider()

# ── Trends summary ────────────────────────────────────────────────────────
st.markdown('<div class="section-heading">📊 Trends Summary</div>', unsafe_allow_html=True)

_qperf = (
    rows.groupby("query")
    .agg(videos=("views_per_day", "count"), avg_vpd=("views_per_day", "mean"), max_vpd=("views_per_day", "max"))
    .sort_values("avg_vpd", ascending=False)
    .reset_index()
)
_top_ch = rows.groupby("channel")["views_per_day"].mean().sort_values(ascending=False).head(3)

_q_lines = "".join(
    f'<li><b>{r["query"]}</b> — {int(r["videos"])} videos · '
    f'avg {r["avg_vpd"]:,.0f} views/day · peak {r["max_vpd"]:,.0f} views/day</li>'
    for _, r in _qperf.iterrows()
)
_ch_lines = "".join(
    f'<li><b>{ch}</b> — avg {vpd:,.0f} views/day</li>'
    for ch, vpd in _top_ch.items()
)

st.markdown(
    '<div class="trends-summary-box">'
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">'
    f'<div><div style="font-weight:700;color:#065f46;margin-bottom:4px;">Search Queries Tracked</div>'
    f'<ul>{_q_lines}</ul></div>'
    f'<div><div style="font-weight:700;color:#065f46;margin-bottom:4px;">Top Channels by Engagement</div>'
    f'<ul>{_ch_lines}</ul></div>'
    '</div></div>',
    unsafe_allow_html=True,
)

st.divider()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ▶️ Filters")
    queries = ["All"] + sorted(rows["query"].unique().tolist())
    sel_query = st.selectbox("Search query", queries)
    sort_by = st.radio("Sort by", ["Views / day", "Total views", "Newest first"])

df = rows.copy()
if sel_query != "All":
    df = df[df["query"] == sel_query]
if sort_by == "Total views":
    df = df.sort_values("views", ascending=False)
elif sort_by == "Newest first":
    df = df.sort_values("days_old", ascending=True)
else:
    df = df.sort_values("views_per_day", ascending=False)

df = df.reset_index(drop=True)


def _video_id(url: str) -> str:
    m = re.search(r"[?&]v=([a-zA-Z0-9_-]{11})", url)
    return m.group(1) if m else ""


def _thumb(vid_id: str) -> str:
    return f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg" if vid_id else ""


# ── Top 3 featured ────────────────────────────────────────────────────────────
st.markdown('<div class="section-heading">🔥 Top Trending Videos</div>', unsafe_allow_html=True)

for i, (_, r) in enumerate(df.head(3).iterrows()):
    vid = _video_id(r["url"])
    col_img, col_info = st.columns([2, 3])
    with col_img:
        if vid:
            st.markdown(
                f'<a href="{r["url"]}" target="_blank">'
                f'<img src="{_thumb(vid)}" style="width:100%;border-radius:10px;"/></a>',
                unsafe_allow_html=True,
            )
        else:
            st.image("https://via.placeholder.com/320x180?text=No+Thumbnail")
    with col_info:
        st.markdown(
            f'<span class="rank-badge">#{i+1}</span>'
            f'<a href="{r["url"]}" target="_blank" style="font-size:1.1em;font-weight:800;color:#111827;text-decoration:none;">'
            f'{r["title"]}</a>',
            unsafe_allow_html=True,
        )
        st.caption(f"📺 {r['channel']}  ·  {r['days_old']} days old")
        m1, m2, m3 = st.columns(3)
        m1.metric("Views / day", f"{r['views_per_day']:,.0f}")
        m2.metric("Total views", f"{int(r['views']):,}")
        m3.metric("Likes", f"{int(r['likes']):,}")
        if r.get("description"):
            st.markdown(
                f'<div class="why-box">{str(r["description"])[:200]}…</div>',
                unsafe_allow_html=True,
            )
    st.divider()

# ── All videos grid ───────────────────────────────────────────────────────────
st.markdown('<div class="section-heading">All Videos</div>', unsafe_allow_html=True)

remaining = df.iloc[3:]
cards_html = '<div class="yt-grid">'
for rank, (_, r) in enumerate(remaining.iterrows(), start=4):
    vid = _video_id(r["url"])
    thumb = _thumb(vid)
    title_short = r["title"][:72] + "…" if len(r["title"]) > 72 else r["title"]
    channel_short = r["channel"][:30]
    cards_html += f"""
    <div class="yt-card">
        <a href="{r['url']}" target="_blank">
            {'<img class="yt-thumb" src="' + thumb + '" />' if thumb else '<div style="background:#f3f4f6;aspect-ratio:16/9;"></div>'}
        </a>
        <div class="yt-body">
            <a class="yt-title" href="{r['url']}" target="_blank">
                <span class="rank-badge">#{rank}</span>{title_short}
            </a>
            <div class="yt-channel">{channel_short}</div>
            <div class="yt-stats">
                <span class="yt-vpd">{r['views_per_day']:,.0f} views/day</span>
                <span class="yt-age">{r['days_old']}d old</span>
                <span class="yt-views">{int(r['views']):,} total</span>
            </div>
        </div>
    </div>"""
cards_html += "</div>"
st.markdown(cards_html, unsafe_allow_html=True)

# ── Channel breakdown chart (collapsible) ─────────────────────────────────────
with st.expander("📊 Channel & Query Breakdown"):
    col_a, col_b = st.columns(2)
    with col_a:
        ch = rows["channel"].value_counts().head(12)
        fig = go.Figure(go.Bar(
            x=ch.values.tolist(), y=ch.index.tolist(), orientation="h",
            marker=dict(color=EMERALD[1], opacity=0.85),
            hovertemplate="<b>%{y}</b><br>%{x} videos<extra></extra>",
        ))
        fig.update_layout(**PLOTLY_LAYOUT,
            title=dict(text="Videos per Channel", font=dict(size=13, color="#065f46")),
            xaxis=dict(showgrid=True, gridcolor="#d1fae5"),
            yaxis=dict(autorange="reversed"), height=360)
        st.plotly_chart(fig, use_container_width=True, key="yt_ch_chart")
    with col_b:
        qc = rows["query"].value_counts()
        fig2 = go.Figure(go.Pie(
            labels=qc.index.tolist(), values=qc.values.tolist(),
            marker=dict(colors=EMERALD, line=dict(color="white", width=2)),
            hole=0.5, textinfo="label+percent",
        ))
        fig2.update_layout(**PLOTLY_LAYOUT,
            title=dict(text="Videos per Search Query", font=dict(size=13, color="#065f46")),
            height=360, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True, key="yt_q_chart")
