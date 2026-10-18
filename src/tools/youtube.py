"""
YouTube Data API v3 tool.

Two-step pattern (unavoidable with this API):
  1. search.list  → returns video IDs matching a query
  2. videos.list  → returns statistics for those IDs (views, likes, duration)

The YouTube search endpoint doesn't return stats, so we always need both calls.
"""
import httpx
import os
import re
from datetime import datetime, timezone, timedelta

# Tool schema in Anthropic's format — this is what the LLM sees when deciding
# whether and how to call this tool.
YOUTUBE_TOOL_SCHEMA = {
    "name": "search_youtube",
    "description": (
        "Search YouTube for videos about Meta/Ray-Ban smart glasses. "
        "Returns videos sorted by engagement velocity (views/day since posting). "
        "Use order='date' to prioritise recent uploads; 'relevance' for best match overall."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query, e.g. 'meta ray-ban glasses pov india'"
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (1–20). Default 10.",
                "default": 10
            },
            "order": {
                "type": "string",
                "enum": ["relevance", "date", "viewCount"],
                "description": "Sort order. Use 'date' to surface the most recent videos.",
                "default": "relevance"
            },
            "published_after_days": {
                "type": "integer",
                "description": "Only return videos published in the last N days. Default 30.",
                "default": 30
            }
        },
        "required": ["query"]
    }
}


def _parse_duration_seconds(duration: str) -> int:
    """Parse ISO 8601 duration like PT1H2M3S → total seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not match:
        return 0
    h, m, s = (int(x or 0) for x in match.groups())
    return h * 3600 + m * 60 + s


def search_youtube(
    query: str,
    max_results: int = 10,
    order: str = "relevance",
    published_after_days: int = 30,
) -> dict:
    """
    Search YouTube and return videos with engagement velocity.
    Returns a compact dict the LLM can read without being overwhelmed.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return {"error": "YOUTUBE_API_KEY not set in .env"}

    published_after = (
        datetime.now(timezone.utc) - timedelta(days=published_after_days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    base = "https://www.googleapis.com/youtube/v3"

    # Step 1: search — get video IDs
    try:
        search_resp = httpx.get(
            f"{base}/search",
            params={
                "key": api_key,
                "q": query,
                "part": "snippet",
                "type": "video",
                "maxResults": min(max_results, 20),
                "order": order,
                "publishedAfter": published_after,
                "relevanceLanguage": "en",
            },
            timeout=15.0,
        )
        search_resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return {"error": f"YouTube search HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"error": f"YouTube search failed: {e}"}

    items = search_resp.json().get("items", [])
    if not items:
        return {"videos": [], "query": query, "count": 0}

    video_ids = [
        item["id"]["videoId"]
        for item in items
        if item.get("id", {}).get("videoId")
    ]
    if not video_ids:
        return {"videos": [], "query": query, "count": 0}

    # Step 2: videos.list — get stats for those IDs
    try:
        stats_resp = httpx.get(
            f"{base}/videos",
            params={
                "key": api_key,
                "id": ",".join(video_ids),
                "part": "statistics,contentDetails,snippet",
            },
            timeout=15.0,
        )
        stats_resp.raise_for_status()
    except Exception as e:
        return {"error": f"YouTube stats fetch failed: {e}"}

    now = datetime.now(timezone.utc)
    videos = []

    for item in stats_resp.json().get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})

        pub_str = snippet.get("publishedAt", "")
        try:
            pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            days_old = max((now - pub_dt).days, 1)
        except Exception:
            days_old = 30

        views = int(stats.get("viewCount", 0))

        videos.append({
            "id": item["id"],
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "published_at": pub_str,
            "views": views,
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "duration_seconds": _parse_duration_seconds(
                item.get("contentDetails", {}).get("duration", "")
            ),
            # engagement velocity — the key ranking signal
            "views_per_day": round(views / days_old, 1),
            "days_old": days_old,
            "description": snippet.get("description", "")[:200],
            "url": f"https://youtube.com/watch?v={item['id']}",
            "query": query,
        })

    videos.sort(key=lambda v: v["views_per_day"], reverse=True)

    return {
        "videos": videos,
        "query": query,
        "count": len(videos),
        "top_views_per_day": videos[0]["views_per_day"] if videos else 0,
    }
