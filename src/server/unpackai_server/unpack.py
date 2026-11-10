"""The unpack pipeline. Every call to Claude in the app goes through this module.

An unpack makes these calls:

1. The extract call reads the source and fills in the dossier fields.
2. The figures calls read the source again and fill in the numbers for the
   figures, with one call for each figure template that the dossier needs.
   The templates have their own calls because the API rejected the grammar
   of a schema with all of them. The server skips the calls when no figure
   fits a template.
3. The compare call links the new ideas to the ideas in earlier dossiers. The
   server skips it when the database has no other finished dossier.
4. The plain-writing call rewrites every prose field with the plain-writing
   skill from .claude/skills/plain-writing/SKILL.md as the system prompt.

Each call is stored in the generations table, and the finished dossier is
stored in the dossiers table.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import anthropic

from .db import Database
from .dossier_schema import (
    COMPARE_SCHEMA,
    DOSSIER_SCHEMA,
    FIGURE_CALL_SCHEMAS,
    KIND_TEMPLATE,
    PLAIN_SCHEMA,
    ShapeMismatch,
    apply_figure_data,
    apply_links,
    merge_prose,
    rewrite_input,
    prose_values,
    without_links,
)
from .safe_logging import REDACTOR
from .secret_store import read_api_key
from .text_check import check_lines

log = logging.getLogger("unpackai.unpack")

# src/server/unpackai_server/unpack.py, so the repository root is three folders up.
REPO_ROOT = Path(__file__).resolve().parents[3]
INDEX_HTML = REPO_ROOT / "src/web/index.html"
PLAIN_WRITING_SKILL = REPO_ROOT / ".claude/skills/plain-writing/SKILL.md"
UNPACK_SKILL = REPO_ROOT / ".claude/skills/unpack/SKILL.md"

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
    # Query strings and fragments don't identify an arXiv paper, so they are
    # dropped before the match and never stored.
    bare = re.split(r"[?#]", url, maxsplit=1)[0]
    m = ARXIV_ID.search(bare)
    if m and ("arxiv.org" in bare or re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", bare)):
        arxiv_id = m.group(1)
        return Source(key=f"arxiv:{arxiv_id}", kind="arxiv", url=f"https://arxiv.org/pdf/{arxiv_id}")
    if not re.match(r"https?://", url, re.I):
        raise UnpackError("The URL must start with http:// or https://.")
    if url.lower().split("?")[0].endswith(".pdf"):
        return Source(key=url, kind="pdf_url", url=url)
    return Source(key=url, kind="web_url", url=url)


def source_from_key(key: str, kind: str) -> Source:
    """Rebuild the source of a stored paper from papers.source, to retry an unpack."""
    if kind == "arxiv":
        return parse_source(key.removeprefix("arxiv:"))
    if kind in ("pdf_url", "web_url"):
        return Source(key=key, kind=kind, url=key)
    raise UnpackError("The server doesn't keep pasted text, so send the text again to POST /api/unpack.")


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

FIGURES_SYSTEM = """You fill in the numbers for the interactive figures of an UnpackAI dossier. UnpackAI is a web app that explains new AI research papers and lab blog posts, and each dossier has figures that let the reader change an input and see the effect.

The page can't run code from you, so it draws each figure from one of these fixed templates:
- "comparison" shows results of several methods on the same metrics.
- "calculator" shows a size or a cost that you get by multiplying the inputs.
- "timeline" shows a schedule over training steps or tokens.
- "steps" shows a pipeline or a calculation done step by step.
- "threshold" shows a score threshold that keeps or drops items.

You get the source, the name of one template, and a JSON list of the figures that the dossier plans for that template, with the index, title, and "What to notice" note of each figure. Return the data for each figure in the list, with the index of the figure in "figure". Leave a figure out when the template doesn't fit it, or when the source doesn't give the numbers it needs.

Rules for the figure data:
- Every number comes from the source, and "source" names the section, table, or figure. Don't guess a value that the source doesn't give. When a template needs example values that the source doesn't give, e.g., example items for a threshold, set made_up_values to true. For a calculator input that the source doesn't give, set from_paper to false.
- A calculator output is the constant times each input raised to its power. For example, a cache size in bytes of layers times tokens times 2 bytes has a power of 1 for both inputs and a constant of 2. Use powers from -4 to 4, and give each input the values from the source as its choices.
- In a comparison, give each method one value for each metric, in the order of the metrics. Mark the method that the source presents as new with is_new. When the source doesn't report a value, write 0 and add the index of the metric to not_reported.
- In steps, set has_value to false and write 0 for a step that has no value.
- Keep names and labels short, e.g., a method or a metric name. Write the explanation in the text of each step, in plain sentences."""

FIGURES_USER = "Fill in the \"{template}\" template for the figures below. The source location is: {location}\n\n{figures}"

COMPARE_SYSTEM = """You compare the new ideas in a paper with the ideas in earlier UnpackAI dossiers. UnpackAI marks each idea in a paper as new, inherited from earlier work, or standard practice, and a link to an earlier dossier shows the reader where an idea came from.

You get the ideas of the new paper and a list of earlier dossiers with their ideas, as JSON. Return a link for each new idea that matches an idea in an earlier dossier, with the indexes and the paper id from the input.

Rules for the links:
- Use "same_idea" when the new paper uses the earlier idea without a change that it presents as its own.
- Use "builds_on" when the new paper changes or extends the earlier idea, and presents the change as new.
- Link only to papers published before the new paper. When a date is missing or unclear, link only when the text of the new idea names the earlier work.
- A shared topic isn't a match. Link two ideas only when they describe the same technique, or when one technique directly changes the other.
- Give each new idea at most one link, to the closest earlier idea. Return an empty list when no idea matches."""

PLAIN_SYSTEM = """You edit the text of UnpackAI dossiers so it follows the plain-writing skill below.

You get a dossier as JSON. Rewrite the prose fields so each one follows the skill, and return the whole dossier in the same shape. The prose fields are the thesis, the highlights, and the title, label, lede, what, replaces, why, heading, text, what_to_notice, and meaning fields, and the not_disclosed and figure_texts items.

Keep these things exactly as they are:
- Every value that isn't a prose field, e.g., a status, an evidence label, a tab id, a number, or a URL
- The number of items in every list, and their order
- Every number, name, and technical term inside the prose, unless the skill asks you to define a term

Each highlight must be an exact phrase from the rewritten thesis. The figure_texts list holds the text of the steps in the figures, so rewrite each item and keep the list the same length.

<plain_writing_skill>
{plain_writing_skill}
</plain_writing_skill>"""


def _read(path: Path, what: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        raise UnpackError(f"The {what} skill isn't at {path.relative_to(REPO_ROOT)}, so the unpack stopped.") from None


# ---------------------------------------------------------------- calls
class Unpacker:
    def __init__(self, db: Database, model: str = "claude-opus-5-5", client_factory: Callable[[str], anthropic.Anthropic] | None = None):
        self.db = db
        self.model = model
        self._client_factory = client_factory or (lambda key: anthropic.Anthropic(api_key=key, max_retries=2))
        self._client: anthropic.Anthropic | None = None
        # The step that is running, or the step where the unpack stopped, for
        # each paper since the server started. The page shows it as progress.
        self.last_step: dict[int, str] = {}

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

    @staticmethod
    def _source_content(source: Source, request: str, cache: bool = False) -> tuple[list, list]:
        """Return the message content that gives Claude the source, and the tools it needs.

        With cache, the document block gets a cache breakpoint, so the next
        call with the same system prompt can read the source from the cache.
        """
        mark = {"cache_control": {"type": "ephemeral"}} if cache else {}
        if source.kind in ("arxiv", "pdf_url"):
            content = [
                {"type": "document", "source": {"type": "url", "url": source.url}, **mark},
                {"type": "text", "text": request.replace("{location}", source.url)},
            ]
            return content, []
        if source.kind == "web_url":
            content = [{"type": "text", "text": f"Read the page at {source.url} with web fetch, and also read the paper or code it links to if it has one. " + request.replace("{location}", source.url)}]
            return content, [{"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 6}]
        content = [
            {"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": source.text}, **mark},
            {"type": "text", "text": request.replace("{location}", "text pasted by the user")},
        ]
        return content, []

    def extract(self, paper_id: int, source: Source) -> dict:
        system = EXTRACT_SYSTEM.format(unpack_skill=_read(UNPACK_SKILL, "unpack"))
        content, tools = self._source_content(source, EXTRACT_USER)
        params: dict[str, Any] = {
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "output_config": {"effort": "high", "format": {"type": "json_schema", "schema": DOSSIER_SCHEMA}},
            "messages": [{"role": "user", "content": content}],
        }
        if tools:
            params["tools"] = tools
        return self._call(paper_id, "extract", **params)

    def figures(self, paper_id: int, source: Source, draft: dict) -> dict:
        """Fill in the data of the figures with one call for each template that the dossier needs.

        The API rejected the grammar of one schema with all five templates,
        so each call reads the source again with one template's schema. The
        system prompt and the source come first in every call, with a cache
        breakpoint, so the later calls can read them from the cache. A failed
        call leaves its figures without data, and the unpack goes on, because
        a figure without data still shows its title and its note.
        """
        groups: dict[str, list[int]] = {}
        for i, f in enumerate(draft["figures"]):
            name = KIND_TEMPLATE.get(f["kind"])
            if name:
                groups.setdefault(name, []).append(i)
        results: dict[str, list] = {}
        for name in FIGURE_CALL_SCHEMAS:
            if name not in groups:
                continue
            plan = [
                {"figure": i, "title": draft["figures"][i]["title"], "what_to_notice": draft["figures"][i]["what_to_notice"]}
                for i in groups[name]
            ]
            request = FIGURES_USER.replace("{template}", name).replace("{figures}", json.dumps(plan, ensure_ascii=False))
            content, tools = self._source_content(source, request, cache=True)
            params: dict[str, Any] = {
                "system": [{"type": "text", "text": FIGURES_SYSTEM}],
                "output_config": {"effort": "high", "format": {"type": "json_schema", "schema": FIGURE_CALL_SCHEMAS[name]}},
                "messages": [{"role": "user", "content": content}],
            }
            if tools:
                params["tools"] = tools
            try:
                result = self._call(paper_id, f"figures_{name}", **params)
            except (UnpackError, anthropic.APIError) as exc:
                log.warning("paper %s: the %s figures call failed, so its figures have no data: %s", paper_id, name, describe_error(exc))
                continue
            # A figure that belongs to another template is dropped.
            results[name] = [item for item in result.get(name) or [] if item.get("figure") in groups[name]]
        return apply_figure_data(draft, results)

    def compare(self, paper_id: int, draft: dict) -> dict:
        earlier = {d["paper_id"]: d for d in self.db.earlier_dossiers(exclude=paper_id)}
        if not earlier or not draft["novelties"]:
            return draft
        ideas = lambda novelties, keys: [{"index": i, **{k: n[k] for k in keys}} for i, n in enumerate(novelties)]  # noqa: E731
        payload = {
            "new_paper": {
                "title": draft["paper"]["title"],
                "published": draft["paper"]["published"],
                "ideas": ideas(draft["novelties"], ("what", "status", "replaces", "why")),
            },
            "earlier_dossiers": [
                {"paper_id": pid, "title": d["title"], "published": d["published"], "ideas": ideas(d["novelties"], ("what", "status", "why"))}
                for pid, d in earlier.items()
            ],
        }
        result = self._call(
            paper_id,
            "compare",
            system=[{"type": "text", "text": COMPARE_SYSTEM}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": COMPARE_SCHEMA}},
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        return apply_links(draft, result["links"], earlier)

    def plain_writing(self, paper_id: int, dossier: dict) -> dict:
        system = PLAIN_SYSTEM.format(plain_writing_skill=_read(PLAIN_WRITING_SKILL, "plain-writing"))
        # The links and the figure data aren't in PLAIN_SCHEMA. The links hold
        # no new prose, and the text of the figure steps goes in a flat list.
        # merge_prose keeps everything else from the original.
        rewritten = self._call(
            paper_id,
            "plain_writing",
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": PLAIN_SCHEMA}},
            messages=[{"role": "user", "content": json.dumps(rewrite_input(dossier), ensure_ascii=False)}],
        )
        try:
            return merge_prose(dossier, rewritten)
        except ShapeMismatch as exc:
            raise UnpackError(f"The plain-writing pass changed the shape of the dossier ({exc}).") from None

    # The schemas that the calls send as output_config.format.
    SCHEMAS = {
        "extract": DOSSIER_SCHEMA,
        **{f"figures_{name}": schema for name, schema in FIGURE_CALL_SCHEMAS.items()},
        "compare": COMPARE_SCHEMA,
        "plain_writing": PLAIN_SCHEMA,
    }

    def _try_schema(self, schema: dict) -> str | None:
        """Send one schema with a tiny token limit. Return the API's error, or None if it accepts the schema."""
        try:
            with self.client().beta.messages.stream(
                model=self.model,
                max_tokens=64,
                thinking={"type": "adaptive"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
                messages=[{"role": "user", "content": "Reply with any JSON that fits the schema."}],
            ) as stream:
                stream.get_final_message()
        except anthropic.BadRequestError as exc:
            return describe_error(exc)
        return None

    def check_schemas(self) -> list[tuple[str, str]]:
        """Check that the API accepts the schema of each call, and return (name, result) pairs.

        The API compiles each schema into a grammar and rejects a grammar that
        is too large. When it rejects a schema, the check sends each top-level
        field of the schema on its own, to show which part is too large. Each
        request stops after 64 output tokens, so the check costs little.
        """
        results = []
        for name, schema in self.SCHEMAS.items():
            problem = self._try_schema(schema)
            results.append((name, problem or "accepted"))
            if problem:
                for key, sub in schema["properties"].items():
                    part = {"type": "object", "properties": {key: sub}, "required": [key], "additionalProperties": False}
                    results.append((f"{name}.{key}", self._try_schema(part) or "accepted"))
        return results

    def run(self, paper_id: int, source: Source) -> None:
        """Run the whole unpack for one paper. Errors are stored, not raised."""
        self.db.set_status(paper_id, "running")
        try:
            self.last_step[paper_id] = "extract"
            draft = self.extract(paper_id, source)
            p = draft["paper"]
            self.db.set_metadata(paper_id, title=p["title"], org=p["org"], published=p["published"], paper_type=p["paper_type"])
            # Figure data that the page couldn't draw is set to null, so the
            # later calls and the stored dossier only have data that works.
            self.last_step[paper_id] = "figures"
            draft = self.figures(paper_id, source, draft)
            self.last_step[paper_id] = "compare"
            draft = self.compare(paper_id, draft)
            self.last_step[paper_id] = "plain_writing"
            final = self.plain_writing(paper_id, draft)
            self.last_step[paper_id] = "text_check"
            problems = text_problems(final)
            version = self.db.add_dossier(paper_id, final, problems)
            self.db.set_status(paper_id, "done")
            log.info("paper %s: stored dossier version %s with %s text problem(s)", paper_id, version, len(problems))
        except Exception as exc:
            self.db.set_status(paper_id, "failed", describe_error(exc))
            log.warning("paper %s: unpack failed: %s", paper_id, describe_error(exc))


def text_problems(dossier: dict) -> list[dict[str, str]]:
    """Run the text check on every prose field of a dossier."""
    return [
        {"field": field, "problem": problem}
        for field, text in prose_values(dossier)
        for _, problem, _ in check_lines([text])
    ]


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
