"""The JSON schema for a generated dossier, and the list of prose fields.

The fields match what index.html shows for each dossier. The prose fields are
the ones that go through the plain-writing pass. Every other field, e.g., a
status, an evidence class, or a number, is kept from the earlier calls, so
the rewrite can't change it.

The compare call returns links between the new ideas and the ideas in earlier
dossiers. apply_links() adds each link to its novelty as an "earlier" field,
which isn't in DOSSIER_SCHEMA because the extract call doesn't fill it in. A
link holds no new prose. It names the earlier paper and copies the earlier
idea's text, which already went through the plain-writing pass.
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

RELATIONS = ["same_idea", "builds_on"]

COMPARE_SCHEMA: dict[str, Any] = _obj(
    {
        "links": _arr(
            _obj(
                {
                    "novelty": {"type": "integer"},
                    "earlier_paper": {"type": "integer"},
                    "earlier_novelty": {"type": "integer"},
                    "relation": {"type": "string", "enum": RELATIONS},
                }
            )
        )
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


def apply_links(dossier: dict, links: list[dict], earlier: dict[int, dict]) -> dict:
    """Add the links from the compare call to a copy of the dossier.

    earlier maps a paper id to {"title", "published", "novelties"} for each
    earlier dossier. A link with an index or a paper id that isn't in the input
    is dropped, and each novelty keeps only its first link. A novelty that is
    the same idea as an earlier one is marked as inherited.
    """
    import copy

    out = copy.deepcopy(dossier)
    novelties = out["novelties"]
    for n in novelties:
        n["earlier"] = None
    for link in links:
        i, j = link.get("novelty"), link.get("earlier_novelty")
        e = earlier.get(link.get("earlier_paper"))
        relation = link.get("relation")
        if relation not in RELATIONS or e is None:
            continue
        if not (isinstance(i, int) and 0 <= i < len(novelties)) or novelties[i]["earlier"] is not None:
            continue
        if not (isinstance(j, int) and 0 <= j < len(e["novelties"])):
            continue
        novelties[i]["earlier"] = {
            "paper_id": link["earlier_paper"],
            "title": e["title"],
            "published": e["published"],
            "idea": e["novelties"][j]["what"],
            "relation": relation,
        }
        if relation == "same_idea" and novelties[i]["status"] == "novel":
            novelties[i]["status"] = "inh"
    return out


def without_links(dossier: dict) -> dict:
    """Return a copy of the dossier without the links, in the shape of DOSSIER_SCHEMA."""
    out = dict(dossier)
    out["novelties"] = [{k: v for k, v in n.items() if k != "earlier"} for n in dossier["novelties"]]
    return out


def prose_values(doc: dict) -> list[tuple[str, str]]:
    """Return (path, text) for every prose value, for the text checks."""
    vals = []
    for path in PROSE_FIELDS:
        for i, (c, k) in enumerate(_get_all(doc, path.split("."))):
            vals.append((f"{path}#{i}", c[k]))
    return vals


def shape_problem(value: Any, schema: dict[str, Any], path: str = "") -> str | None:
    """Return the first place where the value doesn't match the schema, or None.

    The check covers the parts of JSON schema that DOSSIER_SCHEMA uses, i.e.,
    objects with required keys and no other keys, arrays, strings, integers,
    booleans, and enums. The server uses it on dossiers from export files,
    because those dossiers didn't come from a call with structured output.
    """
    where = path or "the dossier"
    t = schema.get("type")
    if t == "object":
        if not isinstance(value, dict):
            return f"{where} must be an object"
        for key in schema["required"]:
            if key not in value:
                return f"{where} has no {key!r} field"
        for key in value:
            if key not in schema["properties"]:
                return f"{where} has an unknown field {key!r}"
        for key, sub in schema["properties"].items():
            problem = shape_problem(value[key], sub, f"{path}.{key}" if path else key)
            if problem:
                return problem
        return None
    if t == "array":
        if not isinstance(value, list):
            return f"{where} must be a list"
        for i, item in enumerate(value):
            problem = shape_problem(item, schema["items"], f"{path}[{i}]")
            if problem:
                return problem
        return None
    if t == "string" and not isinstance(value, str):
        return f"{where} must be a string"
    if t == "boolean" and not isinstance(value, bool):
        return f"{where} must be true or false"
    if t == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return f"{where} must be a whole number"
    if "enum" in schema and value not in schema["enum"]:
        return f"{where} must be one of {', '.join(schema['enum'])}"
    return None
