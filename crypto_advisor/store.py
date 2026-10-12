"""SQLite persistence: HTTP response cache, point-in-time snapshots, run history.

Two things matter here beyond simple caching:

1. **Rate-limit survival.** Public APIs throttle hard. Every response is cached
   with a TTL and an optional stale fallback, so a throttled provider degrades
   into "slightly old data" instead of a crashed run.

2. **Point-in-time snapshots.** This is the tool's defence against survivorship
   bias. If you only ever look at today's top 150 coins, every historical
   analysis is distorted, because the coins that died have silently vanished
   from the list. By recording the universe as it actually looked on each run
   date, you build an honest history from the day you start running this.

Standard library only: ``sqlite3``.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS http_cache (
    key         TEXT PRIMARY KEY,
    provider    TEXT NOT NULL,
    url         TEXT NOT NULL,
    status      INTEGER NOT NULL,
    body        TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    ttl_s       INTEGER NOT NULL,
    bytes       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_http_cache_provider ON http_cache(provider);
CREATE INDEX IF NOT EXISTS idx_http_cache_fetched  ON http_cache(fetched_at);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_date TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    rank          INTEGER,
    price_usd     REAL,
    market_cap    REAL,
    volume_24h    REAL,
    taken_at      TEXT NOT NULL,
    payload       TEXT NOT NULL,
    PRIMARY KEY (snapshot_date, symbol)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_symbol ON snapshots(symbol);

CREATE TABLE IF NOT EXISTS runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL,
    warnings    TEXT NOT NULL DEFAULT '[]',
    summary     TEXT
);

CREATE TABLE IF NOT EXISTS scores (
    run_id      INTEGER NOT NULL,
    symbol      TEXT NOT NULL,
    composite   REAL,
    grade       TEXT,
    disqualified INTEGER NOT NULL DEFAULT 0,
    payload     TEXT NOT NULL,
    PRIMARY KEY (run_id, symbol),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_scores_symbol ON scores(symbol);

CREATE TABLE IF NOT EXISTS fetch_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL,
    provider    TEXT NOT NULL,
    url         TEXT NOT NULL,
    outcome     TEXT NOT NULL,
    http_status INTEGER,
    ms          INTEGER,
    detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_fetch_log_at ON fetch_log(at);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(text: str) -> datetime:
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class CacheEntry:
    key: str
    provider: str
    url: str
    status: int
    body: str
    fetched_at: datetime
    ttl_s: int

    @property
    def age_s(self) -> float:
        return (utcnow() - self.fetched_at).total_seconds()

    def is_fresh(self) -> bool:
        return self.age_s <= self.ttl_s

    def json(self) -> Any:
        return json.loads(self.body)


class Store:
    """Thin wrapper around a SQLite database. Not thread-safe; one per process."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.commit()
        finally:
            self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- HTTP cache -----------------------------------------------------------

    def get_cache(self, key: str) -> CacheEntry | None:
        row = self.conn.execute(
            "SELECT key, provider, url, status, body, fetched_at, ttl_s "
            "FROM http_cache WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return CacheEntry(
            key=row["key"],
            provider=row["provider"],
            url=row["url"],
            status=row["status"],
            body=row["body"],
            fetched_at=parse_iso(row["fetched_at"]),
            ttl_s=row["ttl_s"],
        )

    def put_cache(
        self, key: str, provider: str, url: str, status: int, body: str, ttl_s: int
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO http_cache "
            "(key, provider, url, status, body, fetched_at, ttl_s, bytes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (key, provider, url, status, body, iso(utcnow()), ttl_s, len(body)),
        )
        self.conn.commit()

    def purge_cache(self, provider: str | None = None) -> int:
        if provider:
            cur = self.conn.execute("DELETE FROM http_cache WHERE provider = ?", (provider,))
        else:
            cur = self.conn.execute("DELETE FROM http_cache")
        self.conn.commit()
        return cur.rowcount

    def cache_stats(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT provider, COUNT(*) AS entries, "
            "SUM(bytes) AS bytes, MAX(fetched_at) AS newest "
            "FROM http_cache GROUP BY provider ORDER BY provider"
        ).fetchall()

    # -- fetch log ------------------------------------------------------------

    def log_fetch(
        self,
        provider: str,
        url: str,
        outcome: str,
        http_status: int | None = None,
        ms: int | None = None,
        detail: str | None = None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO fetch_log (at, provider, url, outcome, http_status, ms, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (iso(utcnow()), provider, url[:500], outcome, http_status, ms, detail),
        )
        self.conn.commit()

    def recent_fetches(self, limit: int = 30) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT at, provider, outcome, http_status, ms, url "
            "FROM fetch_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    # -- runs -----------------------------------------------------------------

    def start_run(self) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs (started_at, status) VALUES (?, 'running')", (iso(utcnow()),)
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(
        self,
        run_id: int,
        status: str,
        warnings: Iterable[str] = (),
        summary: str | None = None,
    ) -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at = ?, status = ?, warnings = ?, summary = ? "
            "WHERE run_id = ?",
            (iso(utcnow()), status, json.dumps(list(warnings)), summary, run_id),
        )
        self.conn.commit()

    def last_run(self) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM runs ORDER BY run_id DESC LIMIT 1"
        ).fetchone()

    # -- snapshots ------------------------------------------------------------

    def save_snapshot(self, snapshot_date: str, records: list[dict[str, Any]]) -> int:
        """Persist the universe as it looked on ``snapshot_date`` (YYYY-MM-DD)."""
        now = iso(utcnow())
        rows = [
            (
                snapshot_date,
                rec["symbol"],
                rec.get("rank"),
                rec.get("price_usd"),
                rec.get("market_cap"),
                rec.get("volume_24h"),
                now,
                json.dumps(rec, default=str),
            )
            for rec in records
        ]
        self.conn.executemany(
            "INSERT OR REPLACE INTO snapshots "
            "(snapshot_date, symbol, rank, price_usd, market_cap, volume_24h, taken_at, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def snapshot_dates(self) -> list[str]:
        return [
            r["snapshot_date"]
            for r in self.conn.execute(
                "SELECT DISTINCT snapshot_date FROM snapshots ORDER BY snapshot_date"
            )
        ]

    def load_snapshot(self, snapshot_date: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT symbol, rank, price_usd, market_cap, volume_24h, payload "
            "FROM snapshots WHERE snapshot_date = ? ORDER BY rank",
            (snapshot_date,),
        ).fetchall()

    def symbol_history(self, symbol: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT snapshot_date, rank, price_usd, market_cap, volume_24h "
            "FROM snapshots WHERE symbol = ? ORDER BY snapshot_date",
            (symbol,),
        ).fetchall()

    # -- scores ---------------------------------------------------------------

    def save_scores(self, run_id: int, records: list[dict[str, Any]]) -> int:
        rows = [
            (
                run_id,
                rec["symbol"],
                rec.get("composite"),
                rec.get("grade"),
                1 if rec.get("disqualified") else 0,
                json.dumps(rec, default=str),
            )
            for rec in records
        ]
        self.conn.executemany(
            "INSERT OR REPLACE INTO scores "
            "(run_id, symbol, composite, grade, disqualified, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def score_history(self, symbol: str, limit: int = 60) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT s.run_id, r.started_at, s.composite, s.grade "
            "FROM scores s JOIN runs r USING (run_id) "
            "WHERE s.symbol = ? ORDER BY s.run_id DESC LIMIT ?",
            (symbol, limit),
        ).fetchall()

    def stats(self) -> dict[str, Any]:
        def one(sql: str) -> Any:
            row = self.conn.execute(sql).fetchone()
            return row[0] if row else 0

        return {
            "cache_entries": one("SELECT COUNT(*) FROM http_cache"),
            "cache_bytes": one("SELECT COALESCE(SUM(bytes), 0) FROM http_cache"),
            "runs": one("SELECT COUNT(*) FROM runs"),
            "snapshot_dates": one("SELECT COUNT(DISTINCT snapshot_date) FROM snapshots"),
            "snapshot_rows": one("SELECT COUNT(*) FROM snapshots"),
            "score_rows": one("SELECT COUNT(*) FROM scores"),
            "fetch_calls": one("SELECT COUNT(*) FROM fetch_log"),
        }
