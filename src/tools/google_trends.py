"""
Google Trends tool via pytrends.

No API key required — pytrends scrapes the public Trends API.
Use to validate whether a topic is genuinely rising in India before
the agent bets on it as a content idea.

Returns interest scores (0–100) averaged over the last 30 days,
plus a rising/stable/falling signal based on the trend slope.
"""

import time
from typing import Optional

GOOGLE_TRENDS_TOOL_SCHEMA = {
    "name": "get_google_trends",
    "description": (
        "Check Google Trends interest scores for keywords, focused on India. "
        "Returns a 0–100 interest score per keyword (100 = peak popularity) and "
        "a trend direction (rising / stable / falling). "
        "Use to validate that a YouTube/Reddit theme is also trending in India before picking it as a content idea. "
        "Pass 2–5 keywords to compare them against each other."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1–5 keywords to check. E.g. ['ray-ban meta glasses', 'smart glasses india']"
            },
            "geo": {
                "type": "string",
                "description": "Country code for geo-filtering. Default 'IN' (India). Use '' for worldwide.",
                "default": "IN"
            },
            "timeframe": {
                "type": "string",
                "description": "Time window. Default 'today 1-m' (last 30 days). Options: 'today 1-m', 'today 3-m', 'today 12-m'.",
                "default": "today 1-m"
            }
        },
        "required": ["keywords"]
    }
}


def _trend_direction(series: list[int]) -> str:
    """Simple slope: compare first-half average to second-half average."""
    if len(series) < 4:
        return "stable"
    mid = len(series) // 2
    first_half = sum(series[:mid]) / mid
    second_half = sum(series[mid:]) / (len(series) - mid)
    diff = second_half - first_half
    if diff > 8:
        return "rising"
    if diff < -8:
        return "falling"
    return "stable"


def get_google_trends(
    keywords: list[str],
    geo: str = "IN",
    timeframe: str = "today 1-m",
) -> dict:
    """Fetch Google Trends interest data for up to 5 keywords."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        return {"error": "pytrends not installed — run: pip install pytrends"}

    # Clamp to 5 keywords (Google Trends limit)
    keywords = keywords[:5]
    if not keywords:
        return {"error": "No keywords provided"}

    try:
        pt = TrendReq(hl="en-US", tz=330, timeout=(10, 25), retries=2, backoff_factor=0.5)
        pt.build_payload(keywords, timeframe=timeframe, geo=geo)
        time.sleep(0.5)  # avoid rate-limit on rapid calls
        df = pt.interest_over_time()
    except Exception as e:
        return {"error": f"Google Trends request failed: {e}"}

    if df is None or df.empty:
        return {
            "error": "No trends data returned — Google may have throttled the request",
            "keywords": keywords,
        }

    results = []
    for kw in keywords:
        if kw not in df.columns:
            continue
        series = df[kw].tolist()
        avg_interest = round(sum(series) / len(series), 1) if series else 0
        peak = max(series) if series else 0
        results.append({
            "keyword": kw,
            "avg_interest": avg_interest,   # 0–100; higher = more searches
            "peak_interest": peak,
            "direction": _trend_direction(series),
            "data_points": len(series),
        })

    results.sort(key=lambda r: r["avg_interest"], reverse=True)

    return {
        "results": results,
        "geo": geo or "worldwide",
        "timeframe": timeframe,
        "count": len(results),
        "note": "Interest scores are relative (100 = peak for this keyword in this period)",
    }
