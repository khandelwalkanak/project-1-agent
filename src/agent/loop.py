"""
Hand-written agentic loop using the Anthropic SDK.

How an agentic loop works (the core concept):
  1. Send the conversation history to the LLM with a list of available tools.
  2. The LLM responds with either:
     a) tool_use blocks → it wants to call one or more tools
     b) end_turn        → it's done; the final text is the answer
  3. For (a): execute the tools, append results to history, go back to step 1.
  4. For (b): return the text.

The LLM is the "brain" — it decides WHAT to search for and WHEN it has enough.
We are just the executor + memory (the messages list is the working memory).

This is architecturally identical to what LangGraph does, but with no framework
magic so you can see every moving part.
"""

import anthropic
import json
import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Tools: each module exports a callable + its JSON schema for the Anthropic API
from tools.youtube import search_youtube, YOUTUBE_TOOL_SCHEMA
from tools.web_search import web_search, WEB_SEARCH_TOOL_SCHEMA
from storage.duckdb_store import DuckDBStore
from prompts.system import SYSTEM_PROMPT

# Map tool name (as the LLM will call it) → Python function
TOOL_REGISTRY: dict[str, callable] = {
    "search_youtube": search_youtube,
    "web_search": web_search,
}

# All tool schemas the LLM can see
TOOL_SCHEMAS = [YOUTUBE_TOOL_SCHEMA, WEB_SEARCH_TOOL_SCHEMA]


def _execute_tool(name: str, inputs: dict, store: DuckDBStore) -> dict:
    """
    Execute one tool call and persist results to the bronze layer.
    Always returns a dict (never raises) so the LLM gets a clear error message.
    """
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {"error": f"Unknown tool '{name}'. Available: {list(TOOL_REGISTRY)}"}

    try:
        result = fn(**inputs)
    except Exception as e:
        return {"error": f"Tool '{name}' raised an exception: {e}"}

    # Persist raw results — this is the bronze layer write
    if name == "search_youtube" and isinstance(result.get("videos"), list):
        store.upsert_youtube(result["videos"])
    elif name == "web_search" and isinstance(result.get("results"), list):
        store.upsert_web(result["results"], inputs.get("query", ""))

    return result


def run_agent(
    max_steps: int = 15,
    token_budget: int = 80_000,
    model: str = "claude-sonnet-4-6",
) -> str:
    """
    Run the agent loop. Returns the final markdown report as a string.

    max_steps:    max number of LLM calls (each step = 1 LLM call, possibly multiple tool calls)
    token_budget: stop if cumulative tokens exceed this (prevents runaway cost)
    model:        Anthropic model ID
    """
    client = anthropic.Anthropic()
    store = DuckDBStore()
    run_id = str(uuid.uuid4())[:8]

    # The conversation history. Tool results get appended as user messages —
    # this is how the LLM "remembers" what it already searched.
    messages: list[dict] = [
        {
            "role": "user",
            "content": "Start the research now. Follow your workflow: collect, analyse, generate ideas, write the report.",
        }
    ]

    total_tokens = 0

    print(f"\n[{run_id}] Agent starting | model={model} | max_steps={max_steps} | budget={token_budget:,} tokens")
    print("-" * 60)

    for step in range(1, max_steps + 1):
        print(f"[{run_id}] Step {step}/{max_steps} — calling LLM...")

        t0 = time.time()
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
        except anthropic.APIError as e:
            print(f"[{run_id}] LLM API error: {e}")
            break

        latency_ms = (time.time() - t0) * 1000
        in_tok = response.usage.input_tokens
        out_tok = response.usage.output_tokens
        total_tokens += in_tok + out_tok

        store.log_llm_call(run_id, step, in_tok, out_tok, latency_ms, response.stop_reason)

        print(
            f"[{run_id}]   tokens: {in_tok:,} in + {out_tok:,} out "
            f"(cumulative: {total_tokens:,}) | stop_reason: {response.stop_reason} | "
            f"latency: {latency_ms:.0f}ms"
        )

        # Append the assistant's response to history so the next call has context
        messages.append({"role": "assistant", "content": response.content})

        # ── Case 1: LLM is done ──────────────────────────────────────────────
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text") and block.text.strip():
                    summary = store.get_run_summary(run_id)
                    print(
                        f"\n[{run_id}] Done in {step} steps | "
                        f"{summary['total_input_tokens']:,} in + {summary['total_output_tokens']:,} out tokens | "
                        f"{summary['total_latency_ms']:.0f}ms total"
                    )
                    store.close()
                    return block.text
            break  # end_turn but no text block — shouldn't happen

        # ── Token budget check ───────────────────────────────────────────────
        if total_tokens > token_budget:
            print(f"[{run_id}] Token budget exceeded ({total_tokens:,} > {token_budget:,}). Stopping.")
            break

        # ── Case 2: LLM wants to call tools ─────────────────────────────────
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                print(f"[{run_id}]   → tool: {block.name}  inputs: {json.dumps(block.input)[:100]}")
                result = _execute_tool(block.name, block.input, store)

                # Summarise what came back (keeps logs readable)
                if "error" in result:
                    print(f"[{run_id}]     ✗ error: {result['error']}")
                elif block.name == "search_youtube":
                    print(f"[{run_id}]     ✓ {result.get('count', 0)} videos | top {result.get('top_views_per_day', 0):,} views/day")
                elif block.name == "web_search":
                    print(f"[{run_id}]     ✓ {result.get('count', 0)} results")

                # All tool results for this step must be sent in a single user message.
                # The tool_use_id links each result to the tool call that requested it.
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})

    store.close()
    return f"[{run_id}] Agent stopped without producing a final report (check logs above)."


def main() -> None:
    load_dotenv()

    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    max_steps = int(os.getenv("MAX_STEPS", "15"))
    token_budget = int(os.getenv("TOKEN_BUDGET", "80000"))

    report = run_agent(max_steps=max_steps, token_budget=token_budget, model=model)

    # Save report to reports/
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"report_{int(time.time())}.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"\nReport saved → {report_path}")
    print("\n" + "=" * 60)
    print(report)


if __name__ == "__main__":
    main()
