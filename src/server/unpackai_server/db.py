"""SQLite storage for everything the server generates.

Tables:
- papers: one row per source (arXiv paper, PDF URL, blog post, or pasted text)
- generations: one row per call to Claude, with the model, token counts, and
  the raw output
- dossiers: each finished dossier, with a version number per paper, and
  "unpack" or "import" as its origin
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 2

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
    origin        TEXT NOT NULL DEFAULT 'unpack' CHECK (origin IN ('unpack', 'import')),
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
        # Version 1 had no origin column, and CREATE TABLE IF NOT EXISTS
        # doesn't add a column to a table that already exists.
        columns = {r["name"] for r in self._conn.execute("PRAGMA table_info(dossiers)")}
        if "origin" not in columns:
            self._conn.execute(
                "ALTER TABLE dossiers ADD COLUMN origin TEXT NOT NULL DEFAULT 'unpack' CHECK (origin IN ('unpack', 'import'))"
            )
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

    def requeue_failed(self, paper_id: int) -> bool:
        """Queue a failed paper again. Return False if the paper isn't failed."""
        with self.tx() as c:
            cur = c.execute(
                "UPDATE papers SET status='queued', error=NULL, updated_at=? WHERE id=? AND status='failed'", (now(), paper_id)
            )
            return cur.rowcount == 1

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

    def list_calls(self, paper_id: int) -> list[dict[str, Any]]:
        """Return each call for the paper without the raw output, which can be long."""
        with self.tx() as c:
            rows = c.execute(
                "SELECT step, model, stop_reason, input_tokens, output_tokens, duration_ms, error, created_at "
                "FROM generations WHERE paper_id = ? ORDER BY id",
                (paper_id,),
            ).fetchall()
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

    def earlier_dossiers(self, exclude: int) -> list[dict[str, Any]]:
        """Return the title, date, and ideas of the latest dossier of every finished paper, except one."""
        with self.tx() as c:
            rows = c.execute(
                "SELECT d.paper_id, d.content FROM dossiers d JOIN papers p ON p.id = d.paper_id "
                "WHERE p.status = 'done' AND d.paper_id != ? "
                "AND d.version = (SELECT MAX(version) FROM dossiers WHERE paper_id = d.paper_id) ORDER BY d.paper_id",
                (exclude,),
            ).fetchall()
        out = []
        for r in rows:
            content = json.loads(r["content"])
            out.append({
                "paper_id": r["paper_id"],
                "title": content["paper"]["title"],
                "published": content["paper"]["published"],
                "novelties": content["novelties"],
            })
        return out

    def later_links(self, paper_id: int) -> list[dict[str, Any]]:
        """Return the ideas in other finished dossiers that link to an idea in this paper."""
        out = []
        for d in self.earlier_dossiers(exclude=paper_id):
            for n in d["novelties"]:
                link = n.get("earlier")
                if link and link["paper_id"] == paper_id:
                    out.append({
                        "paper_id": d["paper_id"],
                        "title": d["title"],
                        "published": d["published"],
                        "idea": n["what"],
                        "earlier_idea": link["idea"],
                        "relation": link["relation"],
                    })
        return out

    def finished_dossiers(self, paper_ids: list[int] | None = None) -> list[dict[str, Any]]:
        """Return the source and the latest dossier of each finished paper, or of the given papers."""
        with self.tx() as c:
            rows = c.execute(
                "SELECT p.id, p.source, p.source_kind, d.version, d.content FROM papers p JOIN dossiers d ON d.paper_id = p.id "
                "WHERE p.status = 'done' AND d.version = (SELECT MAX(version) FROM dossiers WHERE paper_id = p.id) ORDER BY p.id"
            ).fetchall()
        wanted = None if paper_ids is None else set(paper_ids)
        return [
            {"paper_id": r["id"], "source": r["source"], "source_kind": r["source_kind"], "version": r["version"], "content": json.loads(r["content"])}
            for r in rows
            if wanted is None or r["id"] in wanted
        ]

    def source_keys(self) -> dict[int, str]:
        """Map each paper id to its source key."""
        with self.tx() as c:
            return {r["id"]: r["source"] for r in c.execute("SELECT id, source FROM papers")}

    def import_papers(self, items: list[dict[str, Any]], finish) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Store papers and dossiers from an export file in one transaction.

        Each item has a source, a source_kind, a dossier, and its text
        problems. A paper whose source is already in the library is skipped,
        unless its unpack failed. Then the imported dossier replaces the
        failed unpack. After the papers are stored, finish(dossier, paper_id,
        ids) returns the dossier to store, where ids maps the source of every
        finished paper to its id, so the links between dossiers can be set.
        Return the lists of added and skipped papers.
        """
        added, skipped, stored = [], [], []
        with self.tx() as c:
            for item in items:
                meta = item["dossier"]["paper"]
                fields = (meta["title"], meta["org"], meta["published"], meta["paper_type"], now())
                row = c.execute("SELECT id, status FROM papers WHERE source = ?", (item["source"],)).fetchone()
                if row and row["status"] != "failed":
                    skipped.append({"paper_id": row["id"], "source": item["source"], "title": meta["title"]})
                    continue
                if row:
                    c.execute(
                        "UPDATE papers SET status='done', error=NULL, title=?, org=?, published=?, paper_type=?, updated_at=? WHERE id=?",
                        (*fields, row["id"]),
                    )
                    paper_id = row["id"]
                else:
                    paper_id = c.execute(
                        "INSERT INTO papers (source, source_kind, title, org, published, paper_type, status, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, 'done', ?, ?)",
                        (item["source"], item["source_kind"], *fields, now()),
                    ).lastrowid
                stored.append((paper_id, item))
                added.append({"paper_id": paper_id, "source": item["source"], "title": meta["title"]})
            ids = {r["source"]: r["id"] for r in c.execute("SELECT id, source FROM papers WHERE status = 'done'")}
            for paper_id, item in stored:
                (latest,) = c.execute("SELECT COALESCE(MAX(version), 0) FROM dossiers WHERE paper_id = ?", (paper_id,)).fetchone()
                c.execute(
                    "INSERT INTO dossiers (paper_id, version, content, text_problems, origin, created_at) VALUES (?, ?, ?, ?, 'import', ?)",
                    (paper_id, latest + 1, json.dumps(finish(item["dossier"], paper_id, ids)), json.dumps(item["text_problems"]), now()),
                )
        return added, skipped

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
