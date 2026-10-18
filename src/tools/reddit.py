"""
Reddit search tool — powered by Tavily with site:reddit.com targeting.

Reddit's API now requires approval for app creation, so we query Reddit's
public content through Tavily (which already indexes it) using site:reddit.com.

Subreddits targeted via search queries:
  - Ray-Ban Meta specific : r/RayBanMeta, r/AIGlasses, r/smartglasses
  - Wearable/tech         : r/wearables, r/gadgets
  - India communities     : r/india, r/IndianGaming, r/TechIndia

Requires: TAVILY_API_KEY (already used by web_search tool)
"""

import os
import httpx

RAYBAN_META_SUBREDDITS = [
    "RayBanMeta",
    "AIGlasses",
    "smartglasses",
    "wearables",
    "gadgets",
    "india",
    "IndianGaming",
    "TechIndia",
]

REDDIT_TOOL_SCHEMA = {
    "name": "search_reddit",
    "description": (
        "Search Reddit posts about Meta Ray-Ban smart glasses using Tavily. "
        "Targets specific subreddits: r/RayBanMeta, r/AIGlasses, r/smartglasses, "
        "r/wearables, r/gadgets, r/india, r/IndianGaming, r/TechIndia. "
        "Returns post titles, snippets, and URLs ranked by relevance. "
        "Use to find community discussions, reviews, and sentiment not on YouTube."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query, e.g. 'ray-ban meta glasses review india'"
            },
            "subreddit": {
                "type": "string",
                "description": (
                    "Target a specific subreddit (without r/), e.g. 'RayBanMeta'. "
                    "Leave empty to search across all configured subreddits."
                ),
                "default": ""
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (1–10). Default 8.",
                "default": 8
            },
        },
        "required": ["query"]
    },
}


def _tavily_search(api_key: str, query: str, max_results: int) -> list[dict]:
    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": min(max_results, 10),
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
    except Exception as e:
        return []

    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", "")[:400],
            "published_date": r.get("published_date", ""),
            "subreddit": _extract_subreddit(r.get("url", "")),
        }
        for r in resp.json().get("results", [])
        if "reddit.com" in r.get("url", "")
    ]


def _extract_subreddit(url: str) -> str:
    """Pull subreddit name from a reddit.com URL."""
    parts = url.split("/")
    try:
        idx = parts.index("r")
        return parts[idx + 1] if idx + 1 < len(parts) else ""
    except ValueError:
        return ""


def search_reddit(
    query: str,
    subreddit: str = "",
    max_results: int = 8,
) -> dict:
    """
    Search Reddit via Tavily. When subreddit is given, restricts to that
    subreddit. Otherwise searches across all configured subreddits.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"error": "TAVILY_API_KEY not set in .env"}

    if subreddit:
        tavily_query = f"site:reddit.com/r/{subreddit} {query}"
        results = _tavily_search(api_key, tavily_query, max_results)
        return {
            "posts": results,
            "query": query,
            "subreddits_searched": [subreddit],
            "count": len(results),
        }

    # Search across all configured subreddits
    subreddit_filter = " OR ".join(f"site:reddit.com/r/{s}" for s in RAYBAN_META_SUBREDDITS)
    tavily_query = f"({subreddit_filter}) {query}"
    results = _tavily_search(api_key, tavily_query, max_results)

    subreddits_hit = list({p["subreddit"] for p in results if p["subreddit"]})

    return {
        "posts": results,
        "query": query,
        "subreddits_searched": RAYBAN_META_SUBREDDITS,
        "subreddits_with_results": subreddits_hit,
        "count": len(results),
    }
