"""The unpack pipeline. Every call to Claude in the app goes through this module.

An unpack makes two calls:

1. The extract call reads the source and fills in the dossier fields.
2. The plain-writing call rewrites every prose field with the plain-writing
   skill from .claude/skills/plain-writing/SKILL.md as the system prompt.

Each call is stored in the generations table, and the finished dossier is
stored in the dossiers table.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import anthropic

from .db import Database
from .dossier_schema import DOSSIER_SCHEMA, ShapeMismatch, merge_prose, prose_values
from .safe_logging import REDACTOR
from .secret_store import read_api_key

log = logging.getLogger("unpackai.unpack")

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAIN_WRITING_SKILL = REPO_ROOT / ".claude/skills/plain-writing/SKILL.md"
UNPACK_SKILL = REPO_ROOT / ".claude/skills/unpack/SKILL.md"
CHECK_TEXT = REPO_ROOT / ".claude/skills/unpack/scripts/check_text.py"

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 64000


class UnpackError(RuntimeError):
    pass


# ---------------------------------------------------------------- sources
@dataclass(frozen=True)
class Source:
    key: str  # unique key stored in papers.source
    kind: str  # arxiv, pdf_url, web_url, or text
    url: str | None = None
    text: str | None = None


ARXIV_ID = re.compile(r"(?:arxiv\.org/(?:abs|pdf|html)/)?(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?/?$", re.I)


def parse_source(url: str | None = None, text: str | None = None) -> Source:
    if text:
        digest = hashlib.sha256(text.encode()).hexdigest()[:16]
        return Source(key=f"text:{digest}", kind="text", text=text)
    if not url:
        raise UnpackError("Send a URL, an arXiv id, or the text of the paper.")
    url = url.strip()
    m = ARXIV_ID.search(url)
    if m and ("arxiv.org" in url or re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", url)):
        arxiv_id = m.group(1)
        return Source(key=f"arxiv:{arxiv_id}", kind="arxiv", url=f"https://arxiv.org/pdf/{arxiv_id}")
    if not re.match(r"https?://", url, re.I):
        raise UnpackError("The URL must start with http:// or https://.")
    if url.lower().split("?")[0].endswith(".pdf"):
        return Source(key=url, kind="pdf_url", url=url)
    return Source(key=url, kind="web_url", url=url)


# ---------------------------------------------------------------- prompts
EXTRACT_SYSTEM = """You fill in a dossier for UnpackAI, a web app that explains new AI research papers and lab blog posts. A dossier shows what is new in the work, what the work reuses from earlier work, and how well the evidence supports each claim.

Follow the steps in the unpack skill below, from "Stage 1" to the end of "Stage 2". You can't edit index.html, so skip Stage 3 and Stage 4, and return the dossier fields as JSON instead.

Rules for the fields:
- Every number must come from the source, and the numbers list must name the section, table, or figure for each number.
- When the source doesn't disclose something, add it to not_disclosed. Don't guess the value.
- Each highlight must be an exact phrase from the thesis.
- Each tab id is one lowercase word, and the first tab is "overview" and the last tab is "evidence".
- Each novelty and claim names the tab id that explains it in "where".
- Set uses_made_up_values to true when a figure needs example values that the source doesn't give.

<unpack_skill>
{unpack_skill}
</unpack_skill>"""

EXTRACT_USER = "Unpack the source above into a dossier. The source location is: {location}"

PLAIN_SYSTEM = """You edit the text of UnpackAI dossiers so it follows the plain-writing skill below.

You get a dossier as JSON. Rewrite the prose fields so each one follows the skill, and return the whole dossier in the same shape. The prose fields are the thesis, the highlights, and the title, label, lede, what, replaces, why, heading, text, what_to_notice, and meaning fields, and the not_disclosed items.

Keep these things exactly as they are:
- Every value that isn't a prose field, e.g., a status, an evidence label, a tab id, a number, or a URL
- The number of items in every list, and their order
- Every number, name, and technical term inside the prose, unless the skill asks you to define a term

Each highlight must be an exact phrase from the rewritten thesis.

<plain_writing_skill>
{plain_writing_skill}
</plain_writing_skill>"""


def _read(path: Path, what: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        raise UnpackError(f"The {what} skill isn't at {path.relative_to(REPO_ROOT)}, so the unpack stopped.") from None


def _load_check_text() -> Callable[..., list]:
    spec = importlib.util.spec_from_file_location("unpackai_check_text", CHECK_TEXT)
    if not spec or not spec.loader:
        raise UnpackError("The text checker script is missing.")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.check_lines


# ---------------------------------------------------------------- calls
class Unpacker:
    def __init__(self, db: Database, model: str = "claude-opus-5-5", client_factory: Callable[[str], anthropic.Anthropic] | None = None):
        self.db = db
        self.model = model
        self._client_factory = client_factory or (lambda key: anthropic.Anthropic(api_key=key, max_retries=2))
        self._client: anthropic.Anthropic | None = None

    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            key = read_api_key()
            REDACTOR.add_secret(key)
            self._client = self._client_factory(key)
        return self._client

    def _call(self, paper_id: int, step: str, **params: Any) -> dict:
        """Make one call, store it in the generations table, and return the parsed JSON."""
        started = time.monotonic()
        record: dict[str, Any] = {}
        try:
            messages = params.pop("messages")
            # Web fetch can pause a long turn. Resend the conversation to let
            # the model continue, up to a fixed number of times.
            for _ in range(5):
                with self.client().beta.messages.stream(
                    model=self.model,
                    max_tokens=MAX_TOKENS,
                    thinking={"type": "adaptive"},
                    betas=[FALLBACK_BETA],
                    fallbacks="default",
                    messages=messages,
                    **params,
                ) as stream:
                    msg = stream.get_final_message()
                    request_id = stream.request_id
                if msg.stop_reason != "pause_turn":
                    break
                messages = messages + [{"role": "assistant", "content": msg.content}]
            record = {
                "request_id": request_id,
                "stop_reason": msg.stop_reason,
                "input_tokens": msg.usage.input_tokens,
                "output_tokens": msg.usage.output_tokens,
                "cache_read_tokens": msg.usage.cache_read_input_tokens,
            }
            served_by = msg.model
            if msg.stop_reason == "refusal":
                category = getattr(getattr(msg, "stop_details", None), "category", None)
                raise UnpackError(f"Claude declined the request (category: {category}).")
            if msg.stop_reason == "max_tokens":
                raise UnpackError("The response hit the token limit, so the JSON is incomplete.")
            text = next((b.text for b in reversed(msg.content) if b.type == "text"), "")
            record["output"] = text
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                raise UnpackError("The response isn't valid JSON.") from None
            self.db.add_generation(paper_id, step, served_by, duration_ms=int((time.monotonic() - started) * 1000), **record)
            return data
        except Exception as exc:
            self.db.add_generation(
                paper_id, step, self.model,
                duration_ms=int((time.monotonic() - started) * 1000),
                error=describe_error(exc), **record,
            )
            raise

    def extract(self, paper_id: int, source: Source) -> dict:
        system = EXTRACT_SYSTEM.format(unpack_skill=_read(UNPACK_SKILL, "unpack"))
        if source.kind in ("arxiv", "pdf_url"):
            content = [
                {"type": "document", "source": {"type": "url", "url": source.url}},
                {"type": "text", "text": EXTRACT_USER.format(location=source.url)},
            ]
            tools = []
        elif source.kind == "web_url":
            content = [{"type": "text", "text": f"Read the page at {source.url} with web fetch, and also read the paper or code it links to if it has one. " + EXTRACT_USER.format(location=source.url)}]
            tools = [{"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 6}]
        else:
            content = [
                {"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": source.text}},
                {"type": "text", "text": EXTRACT_USER.format(location="text pasted by the user")},
            ]
            tools = []
        params: dict[str, Any] = {
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "output_config": {"effort": "high", "format": {"type": "json_schema", "schema": DOSSIER_SCHEMA}},
            "messages": [{"role": "user", "content": content}],
        }
        if tools:
            params["tools"] = tools
        return self._call(paper_id, "extract", **params)

    def plain_writing(self, paper_id: int, dossier: dict) -> dict:
        system = PLAIN_SYSTEM.format(plain_writing_skill=_read(PLAIN_WRITING_SKILL, "plain-writing"))
        rewritten = self._call(
            paper_id,
            "plain_writing",
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": DOSSIER_SCHEMA}},
            messages=[{"role": "user", "content": json.dumps(dossier, ensure_ascii=False)}],
        )
        try:
            return merge_prose(dossier, rewritten)
        except ShapeMismatch as exc:
            raise UnpackError(f"The plain-writing pass changed the shape of the dossier ({exc}).") from None

    def run(self, paper_id: int, source: Source) -> None:
        """Run the whole unpack for one paper. Errors are stored, not raised."""
        self.db.set_status(paper_id, "running")
        try:
            draft = self.extract(paper_id, source)
            p = draft["paper"]
            self.db.set_metadata(paper_id, title=p["title"], org=p["org"], published=p["published"], paper_type=p["paper_type"])
            final = self.plain_writing(paper_id, draft)
            check_lines = _load_check_text()
            problems = [
                {"field": field, "problem": problem}
                for field, text in prose_values(final)
                for _, problem, _ in check_lines([text])
            ]
            version = self.db.add_dossier(paper_id, final, problems)
            self.db.set_status(paper_id, "done")
            log.info("paper %s: stored dossier version %s with %s text problem(s)", paper_id, version, len(problems))
        except Exception as exc:
            self.db.set_status(paper_id, "failed", describe_error(exc))
            log.warning("paper %s: unpack failed: %s", paper_id, describe_error(exc))


def describe_error(exc: Exception) -> str:
    """A short error message for the database and the API. It never includes headers."""
    if isinstance(exc, anthropic.APIStatusError):
        msg = f"Claude API error {exc.status_code} ({type(exc).__name__}): {exc.message}"
    elif isinstance(exc, anthropic.APIConnectionError):
        msg = f"Can't reach the Claude API ({type(exc).__name__})."
    elif isinstance(exc, (UnpackError,)) or type(exc).__name__ == "SecretStoreError":
        msg = str(exc)
    else:
        msg = f"Unexpected error ({type(exc).__name__})."
    return REDACTOR.redact(msg)[:1000]
