"""
Bronze-layer storage and LLM call logging, backed by DuckDB.

Bronze = raw results exactly as returned by the API, minimal transformation.
Think of it like a landing zone in your medallion architecture.
Silver and Gold layers will be added in Phase 2 (clustering, idea scoring).

DuckDB is embedded (no server), stores to a single file, and speaks SQL —
comfortable for a data engineer and fast enough for this workload.
"""
import duckdb
import time
from pathlib import Path

DB_PATH = Path("data/social_trends.duckdb")


class DuckDBStore:
    def __init__(self, db_path: str | None = None):
        path = Path(db_path) if db_path else DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(path))
        self._create_tables()

    def _create_tables(self):
        # Bronze: raw YouTube results, deduped on video ID
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bronze_youtube (
                id            VARCHAR PRIMARY KEY,
                title         VARCHAR,
                channel       VARCHAR,
                published_at  VARCHAR,
                views         BIGINT,
                likes         BIGINT,
                comments      BIGINT,
                duration_s    INTEGER,
                views_per_day DOUBLE,
                days_old      INTEGER,
                description   VARCHAR,
                url           VARCHAR,
                query         VARCHAR,
                fetched_at    TIMESTAMP DEFAULT now()
            )
        """)

        # Bronze: raw web search results, deduped on URL
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bronze_web (
                url            VARCHAR PRIMARY KEY,
                title          VARCHAR,
                snippet        VARCHAR,
                published_date VARCHAR,
                query          VARCHAR,
                fetched_at     TIMESTAMP DEFAULT now()
            )
        """)

        # LLM call log — one row per API call; used to track cost/latency
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_call_log (
                log_id        BIGINT,
                run_id        VARCHAR,
                step          INTEGER,
                input_tokens  INTEGER,
                output_tokens INTEGER,
                latency_ms    DOUBLE,
                stop_reason   VARCHAR,
                logged_at     TIMESTAMP DEFAULT now()
            )
        """)

    def upsert_youtube(self, videos: list[dict]) -> None:
        for v in videos:
            self.conn.execute("""
                INSERT OR REPLACE INTO bronze_youtube
                    (id, title, channel, published_at, views, likes, comments,
                     duration_s, views_per_day, days_old, description, url, query)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                v["id"], v["title"], v["channel"], v["published_at"],
                v["views"], v["likes"], v["comments"], v["duration_seconds"],
                v["views_per_day"], v.get("days_old", 0),
                v["description"], v["url"], v["query"],
            ])

    def upsert_web(self, results: list[dict], query: str) -> None:
        for r in results:
            self.conn.execute("""
                INSERT OR REPLACE INTO bronze_web (url, title, snippet, published_date, query)
                VALUES (?, ?, ?, ?, ?)
            """, [r["url"], r["title"], r["snippet"], r.get("published_date", ""), query])

    def log_llm_call(
        self,
        run_id: str,
        step: int,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        stop_reason: str,
    ) -> None:
        self.conn.execute("""
            INSERT INTO llm_call_log (log_id, run_id, step, input_tokens, output_tokens, latency_ms, stop_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [int(time.time() * 1000), run_id, step, input_tokens, output_tokens, latency_ms, stop_reason])

    def get_youtube_bronze(self) -> list[dict]:
        return (
            self.conn.execute("SELECT * FROM bronze_youtube ORDER BY views_per_day DESC")
            .df()
            .to_dict(orient="records")
        )

    def get_run_summary(self, run_id: str) -> dict:
        row = self.conn.execute("""
            SELECT
                count(*)          AS steps,
                sum(input_tokens) AS total_input,
                sum(output_tokens) AS total_output,
                sum(latency_ms)   AS total_latency_ms
            FROM llm_call_log WHERE run_id = ?
        """, [run_id]).fetchone()
        return {
            "steps": row[0], "total_input_tokens": row[1],
            "total_output_tokens": row[2], "total_latency_ms": row[3],
        }

    def close(self) -> None:
        self.conn.close()
