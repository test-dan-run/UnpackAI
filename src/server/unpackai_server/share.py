"""Export files, which move finished dossiers from one library to another.

An export file is JSON in the shape below. It holds the latest dossier of
each paper and no calls to Claude, raw output, errors, or text problems.

    {"format": "unpackai-export", "version": 1, "exported_at": "...",
     "papers": [{"source": "arxiv:2312.00752", "source_kind": "arxiv",
                 "dossier": {...}}]}

Paper ids differ between libraries, so a link to an earlier dossier names the
earlier paper by its source key instead of its id. When a library imports the
file, it sets each link to the id of the paper with that source. A link to a
paper that isn't in the library keeps the title and the idea text, and its
paper id is null, so the page shows the title without a link.

Version 2 added the "data" field to each figure. The server still reads
version 1 files, and it gives their figures no data. On import and export,
clean_figures() sets figure data that the page couldn't draw to null.

An export file comes from another person, so the server treats it like text
from a paper. It checks the shape of every dossier against STORED_DOSSIER_SCHEMA,
it accepts only http and https URLs, and it runs the text check again. If any
paper in the file has a problem, the server stores none of the papers.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .db import Database
from .dossier_schema import RELATIONS, STORED_DOSSIER_SCHEMA, clean_figures, shape_problem, without_links
from .unpack import text_problems

FORMAT = "unpackai-export"
VERSION = 2
READS_VERSIONS = (1, 2)
MAX_PAPERS = 1000
MAX_BYTES = 20 * 1024 * 1024

SOURCE_KEY = {
    "arxiv": re.compile(r"arxiv:\d{4}\.\d{4,5}"),
    "pdf_url": re.compile(r"https?://\S{1,2000}", re.I),
    "web_url": re.compile(r"https?://\S{1,2000}", re.I),
    "text": re.compile(r"text:[0-9a-f]{16}"),
}
LINK_FIELDS = {"source", "title", "published", "idea", "relation"}


class ImportProblem(ValueError):
    pass


def build_export(db: Database, paper_ids: list[int] | None = None) -> dict[str, Any]:
    """Return an export file with the latest dossier of each finished paper, or of the given papers."""
    sources = db.source_keys()
    papers = []
    for row in db.finished_dossiers(paper_ids):
        # A dossier stored before version 2 has figures without data.
        dossier = clean_figures(without_links(row["content"]))
        for n, stored in zip(dossier["novelties"], row["content"]["novelties"]):
            e = stored.get("earlier")
            n["earlier"] = e and {
                "source": sources.get(e["paper_id"]),
                "title": e["title"],
                "published": e["published"],
                "idea": e["idea"],
                "relation": e["relation"],
            }
        papers.append({"source": row["source"], "source_kind": row["source_kind"], "dossier": dossier})
    return {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "papers": papers,
    }


def _check_link(link: Any, where: str) -> str | None:
    if link is None:
        return None
    if not isinstance(link, dict) or set(link) != LINK_FIELDS:
        return f"{where} must have the fields {', '.join(sorted(LINK_FIELDS))}"
    if link["source"] is not None and not isinstance(link["source"], str):
        return f"{where}.source must be a string or null"
    if not all(isinstance(link[k], str) for k in ("title", "published", "idea")):
        return f"{where} must have text in title, published, and idea"
    if link["relation"] not in RELATIONS:
        return f"{where}.relation must be one of {', '.join(RELATIONS)}"
    return None


def _check_paper(p: Any) -> str | None:
    if not isinstance(p, dict) or set(p) != {"source", "source_kind", "dossier"}:
        return "the paper must have the fields source, source_kind, and dossier"
    kind, source = p["source_kind"], p["source"]
    if kind not in SOURCE_KEY:
        return f"source_kind must be one of {', '.join(SOURCE_KEY)}"
    if not isinstance(source, str) or not SOURCE_KEY[kind].fullmatch(source):
        return f"the source isn't a valid {kind} source"
    d = p["dossier"]
    if not isinstance(d, dict) or not isinstance(d.get("novelties"), list) or not all(isinstance(n, dict) for n in d["novelties"]):
        return "the dossier must be an object with a list of novelties"
    for i, n in enumerate(d["novelties"]):
        problem = _check_link(n.get("earlier"), f"novelties[{i}].earlier")
        if problem:
            return problem
    problem = shape_problem(without_links(d), STORED_DOSSIER_SCHEMA)
    if problem:
        return problem
    url = d["paper"]["source_url"]
    if url and not re.match(r"https?://", url, re.I):
        return "paper.source_url must start with http:// or https://"
    return None


def check_export(data: Any) -> list[dict[str, Any]]:
    """Return the papers in an export file, or raise ImportProblem with the first problem."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ImportProblem("The file isn't an UnpackAI export file.")
    if data.get("version") not in READS_VERSIONS:
        raise ImportProblem(f"The file has export version {data.get('version')!r}, and the server reads versions {READS_VERSIONS[0]} to {READS_VERSIONS[-1]}.")
    papers = data.get("papers")
    if not isinstance(papers, list):
        raise ImportProblem("The file has no list of papers.")
    if data["version"] == 1:
        for p in papers:
            figures = p.get("dossier", {}).get("figures") if isinstance(p, dict) and isinstance(p.get("dossier"), dict) else None
            for f in figures if isinstance(figures, list) else []:
                if isinstance(f, dict):
                    f.setdefault("data", None)
    if len(papers) > MAX_PAPERS:
        raise ImportProblem(f"The file has {len(papers)} papers, and the server imports at most {MAX_PAPERS} at a time.")
    for i, p in enumerate(papers):
        problem = _check_paper(p)
        if problem:
            raise ImportProblem(f"Paper {i + 1} in the file has a problem, so the server imported nothing. The problem is that {problem}.")
    return papers


def _set_link_ids(dossier: dict, paper_id: int, ids: dict[str, int]) -> dict:
    out = without_links(dossier)
    for n, imported in zip(out["novelties"], dossier["novelties"]):
        e = imported.get("earlier")
        target = ids.get(e["source"]) if e else None
        n["earlier"] = e and {
            # A paper can't build on itself, so a link to its own source has no id.
            "paper_id": target if target != paper_id else None,
            "title": e["title"],
            "published": e["published"],
            "idea": e["idea"],
            "relation": e["relation"],
        }
    return out


def import_export(db: Database, data: Any) -> dict[str, list[dict[str, Any]]]:
    """Check an export file and store its papers. Return the added and the skipped papers."""
    papers = check_export(data)
    items = []
    for p in papers:
        dossier = clean_figures(p["dossier"])
        items.append({**p, "dossier": dossier, "text_problems": text_problems(without_links(dossier))})
    added, skipped = db.import_papers(items, _set_link_ids)
    return {"added": added, "skipped": skipped}
