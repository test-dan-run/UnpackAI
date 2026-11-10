"""The JSON schema for a generated dossier, and the list of prose fields.

The fields match what index.html shows for each dossier. The prose fields are
the ones that go through the plain-writing pass. Every other field, e.g., a
status, an evidence class, or a number, is kept from the first call, so the
rewrite can't change it.
"""
from __future__ import annotations

from typing import Any

PAPER_TYPES = ["model", "dataset", "systems", "other"]
STATUSES = ["novel", "inh", "std"]
EVIDENCE = [
    "Ablation",
    "Proof",
    "Benchmark",
    "Checked on smaller models",
    "Checked against LLM scores",
    "Self-reported",
]
EVIDENCE_CLASS = ["ok", "warn", "std"]
FIGURE_KINDS = [
    "router_simulation",
    "memory_calculator",
    "schedule_timeline",
    "number_format_heatmap",
    "pipeline_diagram",
    "threshold_tester",
    "method_comparison_simulation",
    "roofline_estimate",
    "block_loop_animation",
    "worked_example",
    "other",
]


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def _arr(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}


S = {"type": "string"}

DOSSIER_SCHEMA: dict[str, Any] = _obj(
    {
        "paper": _obj(
            {
                "title": S,
                "org": S,
                "published": S,
                "source_url": S,
                "paper_type": {"type": "string", "enum": PAPER_TYPES},
            }
        ),
        "thesis": S,
        "highlights": _arr(S),
        "specs": _arr(_obj({"value": S, "label": S})),
        "tabs": _arr(_obj({"id": S, "title": S, "lede": S})),
        "novelties": _arr(
            _obj(
                {
                    "what": S,
                    "status": {"type": "string", "enum": STATUSES},
                    "replaces": S,
                    "why": S,
                    "where": S,
                }
            )
        ),
        "claims": _arr(
            _obj(
                {
                    "heading": S,
                    "text": S,
                    "evidence": {"type": "string", "enum": EVIDENCE},
                    "evidence_class": {"type": "string", "enum": EVIDENCE_CLASS},
                    "where": S,
                }
            )
        ),
        "figures": _arr(
            _obj(
                {
                    "tab": S,
                    "kind": {"type": "string", "enum": FIGURE_KINDS},
                    "title": S,
                    "what_to_notice": S,
                    "uses_made_up_values": {"type": "boolean"},
                }
            )
        ),
        "numbers": _arr(_obj({"value": S, "meaning": S, "source": S})),
        "not_disclosed": _arr(S),
    }
)

# Paths to the prose fields. "[]" means every item of a list.
PROSE_FIELDS = [
    "thesis",
    "highlights[]",
    "specs[].label",
    "tabs[].title",
    "tabs[].lede",
    "novelties[].what",
    "novelties[].replaces",
    "novelties[].why",
    "claims[].heading",
    "claims[].text",
    "figures[].title",
    "figures[].what_to_notice",
    "numbers[].meaning",
    "not_disclosed[]",
]


class ShapeMismatch(ValueError):
    pass


def _get_all(doc: Any, parts: list[str]) -> list[tuple[list, str | int]]:
    """Return (container, key) pairs for every value at the path."""
    head, rest = parts[0], parts[1:]
    if head.endswith("[]"):
        name = head[:-2]
        lst = doc[name] if name else doc
        if not rest:
            return [(lst, i) for i in range(len(lst))]
        out = []
        for item in lst:
            out += _get_all(item, rest)
        return out
    if not rest:
        return [(doc, head)]
    return _get_all(doc[head], rest)


def merge_prose(original: dict, rewritten: dict) -> dict:
    """Copy the prose fields from the rewrite into a copy of the original.

    Raises ShapeMismatch if a list in the rewrite has a different length,
    because then the rewritten text can't be matched to the right item.
    """
    import copy

    out = copy.deepcopy(original)
    for path in PROSE_FIELDS:
        parts = path.split(".")
        dst = _get_all(out, parts)
        src = _get_all(rewritten, parts)
        if len(dst) != len(src):
            raise ShapeMismatch(f"{path}: {len(dst)} values in the original, {len(src)} in the rewrite")
        for (dc, dk), (sc, sk) in zip(dst, src):
            dc[dk] = sc[sk]
    # A highlight is useless if it isn't part of the thesis, because the page
    # marks it by finding it in the thesis text.
    out["highlights"] = [h for h in out["highlights"] if h and h in out["thesis"]]
    return out


def prose_values(doc: dict) -> list[tuple[str, str]]:
    """Return (path, text) for every prose value, for the text checks."""
    vals = []
    for path in PROSE_FIELDS:
        for i, (c, k) in enumerate(_get_all(doc, path.split("."))):
            vals.append((f"{path}#{i}", c[k]))
    return vals
