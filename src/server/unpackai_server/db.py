"""SQLite storage for everything the server generates.

Tables:
- papers: one row per source (arXiv paper, PDF URL, blog post, or pasted text)
- generations: one row per call to Claude, with the model, token counts, and
  the raw output
- dossiers: each finished dossier, with a version number per paper
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id            INTEGER PRIMARY KEY,
    source        TEXT NOT NULL UNIQUE,
    source_kind   TEXT NOT NULL CHECK (source_kind IN ('arxiv', 'pdf_url', 'web_url', 'text')),
    title         TEXT,
    org           TEXT,
    published     TEXT,
    paper_type    TEXT,
    status        TEXT NOT NULL CHECK (status IN ('queued', 'running', 'done', 'failed')),
    error         TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generations (
    id                  INTEGER PRIMARY KEY,
    paper_id            INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    step                TEXT NOT NULL,
    model               TEXT NOT NULL,
    request_id          TEXT,
    stop_reason         TEXT,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    cache_read_tokens   INTEGER,
    duration_ms         INTEGER,
    output              TEXT,
    error               TEXT,
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS generations_paper ON generations(paper_id);

CREATE TABLE IF NOT EXISTS dossiers (
    id            INTEGER PRIMARY KEY,
    paper_id      INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    version       INTEGER NOT NULL,
    content       TEXT NOT NULL,
    text_problems TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    UNIQUE (paper_id, version)
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._lock = threading.Lock()
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(SCHEMA)
        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._conn.commit()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    # ---------- papers ----------
    def upsert_paper(self, source: str, source_kind: str) -> tuple[int, bool]:
        """Return (paper_id, created). An existing failed paper is queued again."""
        with self.tx() as c:
            row = c.execute("SELECT id, status FROM papers WHERE source = ?", (source,)).fetchone()
            if row:
                if row["status"] == "failed":
                    c.execute("UPDATE papers SET status='queued', error=NULL, updated_at=? WHERE id=?", (now(), row["id"]))
                    return row["id"], True
                return row["id"], False
            cur = c.execute(
                "INSERT INTO papers (source, source_kind, status, created_at, updated_at) VALUES (?, ?, 'queued', ?, ?)",
                (source, source_kind, now(), now()),
            )
            return cur.lastrowid, True

    def set_status(self, paper_id: int, status: str, error: str | None = None) -> None:
        with self.tx() as c:
            c.execute("UPDATE papers SET status=?, error=?, updated_at=? WHERE id=?", (status, error, now(), paper_id))

    def set_metadata(self, paper_id: int, *, title: str, org: str, published: str, paper_type: str) -> None:
        with self.tx() as c:
            c.execute(
                "UPDATE papers SET title=?, org=?, published=?, paper_type=?, updated_at=? WHERE id=?",
                (title, org, published, paper_type, now(), paper_id),
            )

    def list_papers(self) -> list[dict[str, Any]]:
        with self.tx() as c:
            rows = c.execute("SELECT * FROM papers ORDER BY created_at DESC, id DESC").fetchall()
        return [dict(r) for r in rows]

    def get_paper(self, paper_id: int) -> dict[str, Any] | None:
        with self.tx() as c:
            row = c.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        return dict(row) if row else None

    # ---------- generations ----------
    def add_generation(self, paper_id: int, step: str, model: str, **fields: Any) -> int:
        cols = ["paper_id", "step", "model", "created_at", *fields.keys()]
        vals = [paper_id, step, model, now(), *fields.values()]
        with self.tx() as c:
            cur = c.execute(
                f"INSERT INTO generations ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals
            )
            return cur.lastrowid

    def list_generations(self, paper_id: int) -> list[dict[str, Any]]:
        with self.tx() as c:
            rows = c.execute("SELECT * FROM generations WHERE paper_id = ? ORDER BY id", (paper_id,)).fetchall()
        return [dict(r) for r in rows]

    # ---------- dossiers ----------
    def add_dossier(self, paper_id: int, content: dict, text_problems: list) -> int:
        with self.tx() as c:
            (latest,) = c.execute("SELECT COALESCE(MAX(version), 0) FROM dossiers WHERE paper_id = ?", (paper_id,)).fetchone()
            c.execute(
                "INSERT INTO dossiers (paper_id, version, content, text_problems, created_at) VALUES (?, ?, ?, ?, ?)",
                (paper_id, latest + 1, json.dumps(content), json.dumps(text_problems), now()),
            )
            return latest + 1

    def latest_dossier(self, paper_id: int) -> dict[str, Any] | None:
        with self.tx() as c:
            row = c.execute(
                "SELECT * FROM dossiers WHERE paper_id = ? ORDER BY version DESC LIMIT 1", (paper_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["content"] = json.loads(d["content"])
        d["text_problems"] = json.loads(d["text_problems"])
        return d
