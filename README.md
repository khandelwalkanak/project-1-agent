# Social Trends Agent — Phase 1

Finds trending Meta (Ray-Ban) smart glasses content and generates India-specific content ideas.

**Architecture:** hand-written agent loop → Anthropic tool use → DuckDB bronze layer → markdown report.

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Three API keys (see below)

---

## API Keys

| Key | Where to get it | Free tier |
|-----|----------------|-----------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/settings/keys) | Pay-per-use |
| `YOUTUBE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → enable "YouTube Data API v3" → Credentials | 10,000 units/day free |
| `TAVILY_API_KEY` | [app.tavily.com](https://app.tavily.com) | 1,000 searches/month free |

---

## Setup

```bash
# 1. Clone / enter the project
cd "Project 1"

# 2. Copy env file and fill in your keys
cp .env.example .env
# edit .env with your three API keys

# 3. Install dependencies (uv creates a .venv automatically)
uv sync

# 4. Run the tests (no API calls, fast)
uv run pytest tests/ -v

# 5. Run the agent
uv run python main.py
```

The agent will:
1. Run 7 searches (5 YouTube + 2 web)
2. Print step-by-step progress with token counts
3. Save the markdown report to `reports/report_<timestamp>.md`
4. Print the report to stdout

---

## Configuration (in `.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Model to use. Swap to `claude-opus-4-8` for higher quality. |
| `MAX_STEPS` | `15` | Max LLM calls before hard stop |
| `TOKEN_BUDGET` | `80000` | Cumulative token limit (input + output) |

---

## Project layout

```
src/
  agent/loop.py        ← hand-written agentic loop (start here)
  tools/youtube.py     ← YouTube Data API v3 search
  tools/web_search.py  ← Tavily web search
  storage/duckdb_store.py  ← bronze layer + LLM call log
  prompts/system.py    ← system prompt (edit to change agent behaviour)
main.py                ← entry point
reports/               ← generated markdown reports
data/                  ← DuckDB file (gitignored)
tests/                 ← unit tests
```

---

## Inspecting the data

DuckDB is just a file. Open it with:

```python
import duckdb
conn = duckdb.connect("data/social_trends.duckdb")

# Top videos by engagement velocity
conn.execute("SELECT title, channel, views_per_day, url FROM bronze_youtube ORDER BY views_per_day DESC LIMIT 10").df()

# LLM call costs
conn.execute("SELECT run_id, sum(input_tokens + output_tokens) as total_tokens, sum(latency_ms) as total_ms FROM llm_call_log GROUP BY run_id").df()
```

---

## Roadmap

- **Phase 2:** Reddit + Google Trends, embeddings clustering, critic loop
- **Phase 3:** Expose as MCP server (`social-trends-mcp`)
- **Phase 4:** LangGraph multi-agent graph with human approval
- **Phase 5:** Weekly scheduled run, tracing, evals
