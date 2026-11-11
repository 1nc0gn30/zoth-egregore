"""Content-addressed response cache.

Why this matters at 50..1000-way fan-out: lenses overlap. A sceptic lens and a
red-team lens asked about the same prompt will often produce byte-identical
reasoning, and a second identical run of the same prompt is pure waste. The key
is sha256(model, system, prompt, temperature, max_tokens) so a cache hit is
only ever returned for a call that would have been identical anyway.

The same digest doubles as the *deduplication* key inside a single wave: two
lenses that hash to the same call are issued once and their answer is shared,
which is what keeps the effective agent count high while the request count
stays low against a 400 RPM ceiling.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path


def call_digest(
    model: str,
    system: str,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    h = hashlib.sha256()
    for part in (model, system, prompt, f"{temperature:.4f}", str(max_tokens)):
        h.update(part.encode("utf-8", "replace"))
        h.update(b"\x1f")
    return h.hexdigest()


class ResponseCache:
    """SQLite-backed, thread-safe, and safe to delete at any time."""

    def __init__(self, path: Path | str | None = None, enabled: bool = True) -> None:
        self.enabled = bool(enabled and path)
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self._conn: sqlite3.Connection | None = None
        if self.enabled:
            self._init()

    def _init(self) -> None:
        if self.path is None:
            self.enabled = False
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), check_same_thread=False, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS responses ("
            "  key TEXT PRIMARY KEY,"
            "  model TEXT, text TEXT, usage TEXT,"
            "  created REAL, last_hit REAL, hits INTEGER DEFAULT 0)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON responses(created)")
        conn.commit()
        self._conn = conn

    # -- api ---------------------------------------------------------------

    def get(self, key: str) -> tuple[str, dict] | None:
        if not self._conn:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT text, usage FROM responses WHERE key = ?", (key,)
            ).fetchone()
            if not row:
                self.misses += 1
                return None
            self._conn.execute(
                "UPDATE responses SET hits = hits + 1, last_hit = ? WHERE key = ?",
                (time.time(), key),
            )
            self._conn.commit()
            self.hits += 1
            try:
                usage = json.loads(row[1] or "{}")
            except Exception:
                usage = {}
            # a cached hit is free
            usage["cost"] = 0.0
            usage["cached"] = True
            return row[0], usage

    def put(self, key: str, model: str, text: str, usage: dict | None) -> None:
        if not self._conn:
            return
        payload = json.dumps(usage or {})
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO responses (key, model, text, usage, created, last_hit, hits)"
                " VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT hits FROM responses WHERE key = ?), 0))",
                (key, model, text, payload, now, now, key),
            )
            self._conn.commit()

    def stats(self) -> dict:
        out = {"enabled": self.enabled, "hits": self.hits, "misses": self.misses}
        if self._conn:
            with self._lock:
                row = self._conn.execute("SELECT COUNT(*), COALESCE(SUM(hits), 0) FROM responses").fetchone()
            out["entries"] = row[0]
            out["reuse_total"] = row[1]
            total = self.hits + self.misses
            out["hit_rate"] = round(self.hits / total, 3) if total else 0.0
        return out

    def purge(self, older_than_s: float | None = None) -> int:
        if not self._conn:
            return 0
        with self._lock:
            if older_than_s is None:
                cur = self._conn.execute("DELETE FROM responses")
            else:
                cur = self._conn.execute(
                    "DELETE FROM responses WHERE created < ?", (time.time() - older_than_s,)
                )
            self._conn.commit()
            return cur.rowcount or 0

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
