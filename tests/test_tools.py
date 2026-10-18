"""
Phase 1 unit tests — fast, no API calls.
Run: uv run pytest tests/ -v
"""
import pytest
from tools.youtube import _parse_duration_seconds, search_youtube
from tools.web_search import web_search


# ── Duration parser ───────────────────────────────────────────────────────────

def test_parse_duration_full():
    assert _parse_duration_seconds("PT1H2M3S") == 3723

def test_parse_duration_minutes_only():
    assert _parse_duration_seconds("PT5M") == 300

def test_parse_duration_seconds_only():
    assert _parse_duration_seconds("PT30S") == 30

def test_parse_duration_empty():
    assert _parse_duration_seconds("") == 0

def test_parse_duration_malformed():
    assert _parse_duration_seconds("P0D") == 0


# ── Tools return clean error dicts when API keys are missing ──────────────────

def test_youtube_missing_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    result = search_youtube("meta glasses")
    assert "error" in result
    assert "YOUTUBE_API_KEY" in result["error"]

def test_web_search_missing_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    result = web_search("meta glasses")
    assert "error" in result
    assert "TAVILY_API_KEY" in result["error"]


# ── Tool schemas are valid ────────────────────────────────────────────────────

def test_youtube_schema_structure():
    from tools.youtube import YOUTUBE_TOOL_SCHEMA
    assert YOUTUBE_TOOL_SCHEMA["name"] == "search_youtube"
    assert "input_schema" in YOUTUBE_TOOL_SCHEMA
    assert "query" in YOUTUBE_TOOL_SCHEMA["input_schema"]["properties"]
    assert "query" in YOUTUBE_TOOL_SCHEMA["input_schema"]["required"]

def test_web_search_schema_structure():
    from tools.web_search import WEB_SEARCH_TOOL_SCHEMA
    assert WEB_SEARCH_TOOL_SCHEMA["name"] == "web_search"
    assert "query" in WEB_SEARCH_TOOL_SCHEMA["input_schema"]["required"]
