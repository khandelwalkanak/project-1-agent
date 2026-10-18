"""
Reddit search tool — OAuth2 client credentials (app-only, no user login).

Subreddits pre-configured by relevance:
  - Ray-Ban Meta specific : r/RayBanMeta, r/AIGlasses, r/smartglasses
  - Wearable/tech         : r/wearables, r/gadgets
  - India communities     : r/india, r/IndianGaming, r/TechIndia

Requires in .env:
    REDDIT_CLIENT_ID     — from https://www.reddit.com/prefs/apps
    REDDIT_CLIENT_SECRET — same page
"""

import os
import time
import httpx

# Subreddits ordered by specificity — most relevant first
RAYBAN_META_SUBREDDITS = [
    "RayBanMeta",    # dedicated Ray-Ban Meta community
    "AIGlasses",     # AI/smart glasses general
    "smartglasses",  # smart glasses broad
    "wearables",     # wearable tech
    "gadgets",       # general gadgets (large, India-heavy)
    "india",         # Indian general community
    "IndianGaming",  # Indian tech & gaming
    "TechIndia",     # Indian tech discussions
]

REDDIT_TOOL_SCHEMA = {
    "name": "search_reddit",
    "description": (
        "Search Reddit for posts about Meta Ray-Ban smart glasses. "
        "When no subreddit is given, searches across the pre-configured list: "
        "r/RayBanMeta, r/AIGlasses, r/smartglasses, r/wearables, r/gadgets, r/india, r/IndianGaming, r/TechIndia. "
        "Returns posts sorted by engagement score (upvotes × comment weight). "
        "Use time_filter='month' for trends; 'week' for very recent buzz."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query, e.g. 'ray-ban meta india review'"
            },
            "subreddit": {
                "type": "string",
                "description": (
                    "Specific subreddit to search (without r/), e.g. 'RayBanMeta'. "
                    "Leave empty to search all configured subreddits."
                ),
                "default": ""
            },
            "max_results": {
                "type": "integer",
                "description": "Max posts to return (1–10 per subreddit). Default 5.",
                "default": 5
            },
            "time_filter": {
                "type": "string",
                "enum": ["day", "week", "month", "year", "all"],
                "description": "Time window for posts. Default 'month'.",
                "default": "month"
            },
        },
        "required": ["query"]
    },
}

# Module-level token cache — token lasts 24 h, reuse within a run
_token_cache: dict = {"token": None, "expires_at": 0.0}

_USER_AGENT = "SocialTrendsAgent/1.0 (by /u/social_trends_bot)"


def _get_token(client_id: str, client_secret: str) -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    resp = httpx.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": _USER_AGENT},
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _token_cache["token"]


def _search_one(
    token: str,
    query: str,
    subreddit: str,
    max_results: int,
    time_filter: str,
) -> list[dict]:
    """Search a single subreddit (or all Reddit if subreddit is empty)."""
    if subreddit:
        url = f"https://oauth.reddit.com/r/{subreddit}/search"
        params = {
            "q": query, "sort": "top", "t": time_filter,
            "limit": min(max_results, 10), "restrict_sr": "true",
        }
    else:
        url = "https://oauth.reddit.com/search"
        params = {
            "q": query, "sort": "top", "t": time_filter,
            "limit": min(max_results, 10),
        }

    try:
        resp = httpx.get(
            url, params=params,
            headers={"Authorization": f"Bearer {token}", "User-Agent": _USER_AGENT},
            timeout=15.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return []
    except Exception:
        return []

    posts = []
    for child in resp.json().get("data", {}).get("children", []):
        d = child.get("data", {})
        score = d.get("score", 0)
        comments = d.get("num_comments", 0)
        posts.append({
            "id": d.get("id", ""),
            "title": d.get("title", ""),
            "subreddit": d.get("subreddit", subreddit),
            "score": score,
            "comments": comments,
            "engagement": score + comments * 3,  # weight comments higher
            "url": f"https://reddit.com{d.get('permalink', '')}",
            "selftext": (d.get("selftext", "") or "")[:300],
            "created_utc": d.get("created_utc", 0),
            "upvote_ratio": d.get("upvote_ratio", 0),
            "flair": d.get("link_flair_text", ""),
        })

    return sorted(posts, key=lambda p: p["engagement"], reverse=True)


def search_reddit(
    query: str,
    subreddit: str = "",
    max_results: int = 5,
    time_filter: str = "month",
) -> dict:
    """
    Search Reddit. If subreddit is empty, iterates through all configured
    subreddits and merges results, deduped by post ID.
    """
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        return {"error": "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set in .env"}

    try:
        token = _get_token(client_id, client_secret)
    except Exception as e:
        return {"error": f"Reddit auth failed: {e}"}

    if subreddit:
        posts = _search_one(token, query, subreddit, max_results, time_filter)
        return {"posts": posts, "query": query, "subreddits_searched": [subreddit], "count": len(posts)}

    # Search all configured subreddits, merge and dedupe
    seen_ids: set[str] = set()
    all_posts: list[dict] = []
    subreddits_hit: list[str] = []

    for sub in RAYBAN_META_SUBREDDITS:
        batch = _search_one(token, query, sub, max_results, time_filter)
        for p in batch:
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                all_posts.append(p)
        if batch:
            subreddits_hit.append(sub)

    all_posts.sort(key=lambda p: p["engagement"], reverse=True)

    return {
        "posts": all_posts[:max_results * 3],  # cap at 3× per-sub limit
        "query": query,
        "subreddits_searched": RAYBAN_META_SUBREDDITS,
        "subreddits_with_results": subreddits_hit,
        "count": len(all_posts),
    }
