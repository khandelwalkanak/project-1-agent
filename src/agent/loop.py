"""
Hand-written agentic loop — Gemini edition (google-genai SDK).

How an agentic loop works:
  1. Send the conversation history to the LLM with available tools.
  2. The LLM responds with either:
     a) function_call parts  → execute them, send results back, repeat
     b) text + STOP          → it's done; that text is the final report
  3. For (a): execute the tools, package results, go back to step 1.
  4. For (b): return the text.
"""

import json
import os
import time
import uuid
from pathlib import Path

from google import genai
from google.genai import types
from dotenv import load_dotenv

from tools.youtube import search_youtube, YOUTUBE_TOOL_SCHEMA
from tools.web_search import web_search, WEB_SEARCH_TOOL_SCHEMA
from tools.reddit import search_reddit, REDDIT_TOOL_SCHEMA
from tools.google_trends import get_google_trends, GOOGLE_TRENDS_TOOL_SCHEMA
from storage.duckdb_store import DuckDBStore
from prompts.system import SYSTEM_PROMPT
from delivery.email_sender import send_report

TOOL_REGISTRY: dict[str, callable] = {
    "search_youtube": search_youtube,
    "web_search": web_search,
    "search_reddit": search_reddit,
    "get_google_trends": get_google_trends,
}

TOOL_SCHEMAS = [YOUTUBE_TOOL_SCHEMA, WEB_SEARCH_TOOL_SCHEMA, REDDIT_TOOL_SCHEMA, GOOGLE_TRENDS_TOOL_SCHEMA]


def _clean_schema(schema: dict) -> dict:
    """Strip fields Gemini's Schema proto doesn't support (e.g. 'default')."""
    cleaned = {k: v for k, v in schema.items() if k != "default"}
    if "properties" in cleaned:
        cleaned["properties"] = {
            k: _clean_schema(v) for k, v in cleaned["properties"].items()
        }
    return cleaned


def _build_gemini_tools() -> list[types.Tool]:
    """Convert our JSON Schema tool definitions to Gemini FunctionDeclarations."""
    declarations = [
        types.FunctionDeclaration(
            name=s["name"],
            description=s["description"],
            parameters=_clean_schema(s["input_schema"]),
        )
        for s in TOOL_SCHEMAS
    ]
    return [types.Tool(function_declarations=declarations)]


def _execute_tool(name: str, inputs: dict, store: DuckDBStore) -> dict:
    """Execute one tool call, persist to bronze layer. Never raises."""
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {"error": f"Unknown tool '{name}'. Available: {list(TOOL_REGISTRY)}"}
    try:
        result = fn(**inputs)
    except Exception as e:
        return {"error": f"Tool '{name}' raised: {e}"}

    if name == "search_youtube" and isinstance(result.get("videos"), list):
        store.upsert_youtube(result["videos"])
    elif name == "web_search" and isinstance(result.get("results"), list):
        store.upsert_web(result["results"], inputs.get("query", ""))
    elif name == "search_reddit" and isinstance(result.get("posts"), list):
        store.upsert_reddit(result["posts"], inputs.get("query", ""))

    return result


def run_agent(
    max_steps: int = 15,
    token_budget: int = 80_000,
    model: str = "gemini-1.5-flash",
) -> str:
    """
    Run the agent loop. Returns the final markdown report as a string.

    max_steps:    max number of LLM calls before hard stop
    token_budget: stop if cumulative tokens exceed this
    model:        Gemini model ID
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    store = DuckDBStore()
    run_id = str(uuid.uuid4())[:8]

    chat = client.chats.create(
        model=model,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=_build_gemini_tools(),
        ),
    )
    total_tokens = 0

    print(f"\n[{run_id}] Agent starting | model={model} | max_steps={max_steps} | budget={token_budget:,} tokens")
    print("-" * 60)

    def _send(msg) -> object:
        """Send a message with exponential backoff on 503."""
        from google.genai.errors import ServerError
        delays = [5, 15, 30, 60]
        for attempt, delay in enumerate(delays + [None], 1):
            try:
                return chat.send_message(msg)
            except ServerError as e:
                if "503" not in str(e) or delay is None:
                    raise
                print(f"[{run_id}] Gemini 503 — retrying in {delay}s (attempt {attempt}/4)…")
                time.sleep(delay)

    # First LLM call — kick off the research workflow
    t0 = time.time()
    response = _send(
        "Start the research now. Follow your workflow: collect, analyse, generate ideas, write the report."
    )

    for step in range(1, max_steps + 1):
        latency_ms = (time.time() - t0) * 1000

        if not response.candidates:
            print(f"[{run_id}] No candidates (safety filter?). Stopping.")
            break

        candidate = response.candidates[0]
        usage = response.usage_metadata
        in_tok = getattr(usage, "prompt_token_count", 0) or 0
        out_tok = getattr(usage, "candidates_token_count", 0) or 0
        total_tokens += in_tok + out_tok

        finish_reason = candidate.finish_reason
        reason_name = finish_reason.name if hasattr(finish_reason, "name") else str(finish_reason)

        store.log_llm_call(run_id, step, in_tok, out_tok, latency_ms, reason_name)

        print(
            f"[{run_id}] Step {step}/{max_steps} — "
            f"{in_tok:,} in + {out_tok:,} out (total: {total_tokens:,}) | "
            f"stop: {reason_name} | {latency_ms:.0f}ms"
        )

        # ── Case 1: LLM wants to call tools ─────────────────────────────────
        tool_calls = [
            part.function_call
            for part in candidate.content.parts
            if part.function_call and part.function_call.name
        ]

        if tool_calls:
            tool_result_parts = []
            for tc in tool_calls:
                inputs = dict(tc.args)
                print(f"[{run_id}]   → tool: {tc.name}  inputs: {json.dumps(inputs)[:100]}")
                result = _execute_tool(tc.name, inputs, store)

                if "error" in result:
                    print(f"[{run_id}]     ✗ {result['error']}")
                elif tc.name == "search_youtube":
                    print(f"[{run_id}]     ✓ {result.get('count', 0)} videos | top {result.get('top_views_per_day', 0):,} views/day")
                elif tc.name == "web_search":
                    print(f"[{run_id}]     ✓ {result.get('count', 0)} results")
                elif tc.name == "search_reddit":
                    subs = ", ".join(result.get("subreddits_with_results", []))
                    print(f"[{run_id}]     ✓ {result.get('count', 0)} posts | subs: {subs or 'none'}")
                elif tc.name == "get_google_trends":
                    summary = ", ".join(
                        f"{r['keyword']} ({r['avg_interest']:.0f} {r['direction']})"
                        for r in result.get("results", [])
                    )
                    print(f"[{run_id}]     ✓ trends: {summary}")

                # Package the result back for the LLM
                tool_result_parts.append(
                    types.Part.from_function_response(
                        name=tc.name,
                        response={"result": json.dumps(result)},
                    )
                )

            if total_tokens > token_budget:
                print(f"[{run_id}] Token budget exceeded ({total_tokens:,}). Stopping.")
                break

            # Send all tool results → triggers next LLM response
            t0 = time.time()
            response = _send(tool_result_parts)
            continue

        # ── Case 2: LLM is done — return the report ──────────────────────────
        if reason_name == "STOP":
            text_parts = [
                part.text for part in candidate.content.parts
                if hasattr(part, "text") and part.text
            ]
            if text_parts:
                text = "\n".join(text_parts)
                summary = store.get_run_summary(run_id)
                print(
                    f"\n[{run_id}] Done in {step} steps | "
                    f"{summary['total_input_tokens'] or 0:,} in + "
                    f"{summary['total_output_tokens'] or 0:,} out | "
                    f"{summary['total_latency_ms'] or 0:.0f}ms total"
                )
                store.close()
                return text

        break  # Unexpected finish reason (MAX_TOKENS, SAFETY, etc.)

    store.close()
    return f"[{run_id}] Agent stopped without a final report (check logs above)."


def main() -> None:
    load_dotenv()

    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    max_steps = int(os.getenv("MAX_STEPS", "15"))
    token_budget = int(os.getenv("TOKEN_BUDGET", "80000"))

    report = run_agent(max_steps=max_steps, token_budget=token_budget, model=model)

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"report_{int(time.time())}.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"\nReport saved → {report_path}")
    send_report(report)
    print("\n" + "=" * 60)
    print(report)


if __name__ == "__main__":
    main()
