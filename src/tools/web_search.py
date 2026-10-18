"""
Tavily web search tool.

Tavily is purpose-built for LLM agents — it returns clean, pre-extracted
snippets (no scraping boilerplate) and respects ToS. Good fallback when
YouTube doesn't have what we need (Reddit threads, news, creator blogs).
"""
import httpx
import os

WEB_SEARCH_TOOL_SCHEMA = {
    "name": "web_search",
    "description": (
        "Search the web for articles, creator discussions, and news about Meta smart glasses. "
        "Useful for finding trends not yet on YouTube (Reddit threads, blogs, news). "
        "Returns title, URL, and a clean text snippet."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results (1–10). Default 5.",
                "default": 5
            }
        },
        "required": ["query"]
    }
}


def web_search(query: str, max_results: int = 5) -> dict:
    """Call Tavily and return a compact list of results."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"error": "TAVILY_API_KEY not set in .env"}

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
    except httpx.HTTPStatusError as e:
        return {"error": f"Tavily HTTP {e.response.status_code}"}
    except Exception as e:
        return {"error": f"Web search failed: {e}"}

    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            # truncate snippet so the LLM context doesn't blow up
            "snippet": r.get("content", "")[:400],
            "published_date": r.get("published_date", ""),
        }
        for r in resp.json().get("results", [])
    ]

    return {"results": results, "query": query, "count": len(results)}
