"""Shared constants, CSS/JS injection, and DuckDB loader for all dashboard pages."""

from pathlib import Path
import duckdb
import streamlit as st

# ── Color palette ─────────────────────────────────────────────────────────────
EMERALD = ["#065f46", "#059669", "#10b981", "#34d399", "#6ee7b7", "#a7f3d0"]

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, -apple-system, sans-serif", color="#111827"),
    margin=dict(l=16, r=16, t=36, b=16),
    hoverlabel=dict(bgcolor="white", bordercolor="#6ee7b7", font_color="#111827"),
)

# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
:root { --cx: 50%; --cy: 30%; }

[data-testid="stAppViewContainer"] {
    background: radial-gradient(
        ellipse 70% 55% at var(--cx) var(--cy),
        #d1fae5 0%, #ecfdf5 20%, #ffffff 55%
    ) !important;
}

div[data-testid="metric-container"] {
    background: rgba(240, 253, 244, 0.85);
    border: 1px solid #6ee7b7;
    border-radius: 12px;
    padding: 18px 20px !important;
}

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
.badge-youtube    { background: #fee2e2; color: #991b1b; }
.badge-reddit     { background: #ffedd5; color: #9a3412; }
.badge-web        { background: #dbeafe; color: #1e40af; }
.badge-trends     { background: #f3e8ff; color: #6b21a8; }

.hook-box {
    background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
    border-left: 4px solid #10b981;
    padding: 12px 18px; border-radius: 0 10px 10px 0;
    font-style: italic; color: #065f46;
    margin: 10px 0 14px 0; line-height: 1.6; font-size: 0.95em;
}

.why-box {
    background: #f9fafb; border: 1px solid #d1fae5; border-radius: 8px;
    padding: 10px 16px; color: #374151; font-size: 0.88em; line-height: 1.6; margin-top: 6px;
}

.hashtags { color: #059669; font-size: 0.82em; line-height: 1.8; }

.section-heading {
    font-size: 1.05em; font-weight: 700; color: #064e3b;
    margin: 24px 0 12px 0; padding-bottom: 8px;
    border-bottom: 2px solid #6ee7b7; letter-spacing: 0.3px;
}

.report-header {
    background: linear-gradient(135deg, #065f46 0%, #059669 60%, #10b981 100%);
    border-radius: 14px; padding: 26px 32px; margin-bottom: 20px; color: white;
    box-shadow: 0 4px 24px rgba(5, 150, 105, 0.18);
}
.report-header h1 { margin: 0 0 6px 0; font-size: 1.65em; font-weight: 800; color: white; }
.report-header .sub { color: #a7f3d0; font-size: 0.88em; }

.source-header {
    border-radius: 14px; padding: 22px 28px; margin-bottom: 20px;
    color: white; box-shadow: 0 4px 20px rgba(0,0,0,0.12);
}
.source-header h1 { margin: 0 0 4px 0; font-size: 1.5em; font-weight: 800; color: white; }
.source-header .sub { font-size: 0.85em; opacity: 0.85; }
.source-yt   { background: linear-gradient(135deg, #991b1b 0%, #ef4444 100%); }
.source-rd   { background: linear-gradient(135deg, #9a3412 0%, #f97316 100%); }
.source-web  { background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); }
</style>
"""

_JS = """
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
"""


def inject_ui() -> None:
    """Inject shared CSS and cursor-tracking JS. Call once per page."""
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(_JS, unsafe_allow_html=True)


# ── DuckDB ────────────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "data" / "social_trends.duckdb"


def load_db() -> duckdb.DuckDBPyConnection | None:
    """Return a read-only DuckDB connection, or None if the file doesn't exist."""
    if not DB_PATH.exists():
        return None
    try:
        return duckdb.connect(str(DB_PATH), read_only=True)
    except Exception:
        return None


def no_data_notice() -> None:
    st.info(
        "No source data yet. Run the agent first:\n\n"
        "```\nuv run python main.py\n```\n\n"
        "Once run, the raw data collected from each source will appear here.",
        icon="📭",
    )
