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

Each stored figure can carry "data" for one of the figure templates in
FIGURE_TEMPLATES, and the page draws the figure from it. The data holds
numbers and short labels from the paper, never HTML or code, so the page can
escape every value. clean_figures() checks the parts that the JSON schema
can't check, e.g., that each method has one value for each metric, and it
sets the data to null when the page couldn't draw it. A figure without data
shows only its title and its "What to notice" note.

The API compiles each output schema into a grammar, and it rejects a grammar
that is too large. DOSSIER_SCHEMA with the figure templates in it was too
large, and so was one schema with all five templates, while each template on
its own was accepted. So DOSSIER_SCHEMA has no figure data, and the server
makes one figures call for each template that the dossier needs, with the
schema in FIGURE_CALL_SCHEMAS. KIND_TEMPLATE picks the template from the
figure kind that the extract call sets, and apply_figure_data() moves the
data into the figures. The plain-writing call gets the text of the
figure steps as a flat list, in PLAIN_SCHEMA. STORED_DOSSIER_SCHEMA is the
shape of a stored dossier with its figure data, and the server uses it only
to check export files.
"""
from __future__ import annotations

import math
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


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def _arr(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}


S = {"type": "string"}
N = {"type": "number"}


# The fields of each figure template that the page can draw. Every template
# also has "source", which names the section, table, or figure of the paper
# that the numbers come from.
FIGURE_FIELDS: dict[str, dict[str, Any]] = {
    # Bars for each method on one metric at a time, with buttons for the metric.
    "comparison": {
        "metrics": _arr(_obj({"name": S, "unit": S, "higher_is_better": {"type": "boolean"}})),
        "methods": _arr(_obj({"name": S, "is_new": {"type": "boolean"}, "values": _arr(_nullable(N))})),
    },
    # Sliders for the inputs. Each output is constant * product(input ** power).
    "calculator": {
        "inputs": _arr(_obj({"name": S, "unit": S, "choices": _arr(N), "default_index": {"type": "integer"}, "from_paper": {"type": "boolean"}})),
        "outputs": _arr(_obj({"name": S, "unit": S, "constant": N, "powers": _arr(N)})),
    },
    # A value over time in phases, e.g., a learning rate schedule, with a slider for the time.
    "timeline": {
        "x_name": S,
        "x_unit": S,
        "y_name": S,
        "y_unit": S,
        "phases": _arr(_obj({"label": S, "start": N, "end": N, "start_value": N, "end_value": N, "shape": {"type": "string", "enum": ["constant", "linear", "cosine"]}})),
    },
    # A sequence of steps that the reader moves through, with an optional value per step.
    "steps": {
        "value_name": S,
        "value_unit": S,
        "steps": _arr(_obj({"label": S, "text": S, "value": _nullable(N), "details": _arr(_obj({"label": S, "value": S}))})),
    },
    # Example items with a score, and a slider for the threshold that keeps or drops them.
    "threshold": {
        "score_name": S,
        "keep_when": {"type": "string", "enum": ["at_least", "at_most"]},
        "thresholds": _arr(N),
        "default_index": {"type": "integer"},
        "items": _arr(_obj({"label": S, "score": N})),
    },
}

# The shape of the data of a stored figure, with the template's name.
FIGURE_TEMPLATES: dict[str, dict[str, Any]] = {
    name: _obj({"template": {"type": "string", "enum": [name]}, **fields, "source": S}) for name, fields in FIGURE_FIELDS.items()
}

# The template for each figure kind from the extract call. A figure of a kind
# that isn't here gets no data, so it shows its title and its note.
KIND_TEMPLATE = {
    "method_comparison_simulation": "comparison",
    "memory_calculator": "calculator",
    "roofline_estimate": "calculator",
    "schedule_timeline": "timeline",
    "pipeline_diagram": "steps",
    "worked_example": "steps",
    "block_loop_animation": "steps",
    "threshold_tester": "threshold",
}

# The output of each figures call. The API docs say that each union type,
# i.e., anyOf or a nullable field, makes the grammar grow fast, so the schema
# has none, and a missing number is a flag instead of null:
# - comparison: "not_reported" lists the metric indexes without a value
# - steps: "has_value" is false when a step has no value
# apply_figure_data() turns both into nulls in the stored data. "figure" is
# the index of the figure in the dossier.
_CALL_FIELDS = {
    **FIGURE_FIELDS,
    "comparison": {
        **FIGURE_FIELDS["comparison"],
        "methods": _arr(_obj({"name": S, "is_new": {"type": "boolean"}, "values": _arr(N), "not_reported": _arr({"type": "integer"})})),
    },
    "steps": {
        **FIGURE_FIELDS["steps"],
        "steps": _arr(_obj({"label": S, "text": S, "value": N, "has_value": {"type": "boolean"}, "details": _arr(_obj({"label": S, "value": S}))})),
    },
}
FIGURE_CALL_SCHEMAS: dict[str, dict[str, Any]] = {
    name: _obj({name: _arr(_obj({"figure": {"type": "integer"}, "made_up_values": {"type": "boolean"}, **fields, "source": S}))})
    for name, fields in _CALL_FIELDS.items()
}


def _stored_data(name: str, item: dict) -> dict:
    """Turn an item from the figures call into stored figure data."""
    import copy

    data = {"template": name, **{k: copy.deepcopy(v) for k, v in item.items() if k not in ("figure", "made_up_values")}}
    if name == "comparison":
        for m in data.get("methods") or []:
            missing = set(m.pop("not_reported", None) or [])
            m["values"] = [None if j in missing else v for j, v in enumerate(m.get("values") or [])]
    if name == "steps":
        for st in data.get("steps") or []:
            if not st.pop("has_value", True):
                st["value"] = None
    return data

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
    "figures[].data.steps[].text",
]
FIGURE_TEXTS = "figures[].data.steps[].text"


def _with_figure_data(schema: dict[str, Any]) -> dict[str, Any]:
    import copy

    out = copy.deepcopy(schema)
    figure = out["properties"]["figures"]["items"]
    figure["properties"]["data"] = _nullable({"anyOf": list(FIGURE_TEMPLATES.values())})
    figure["required"].append("data")
    return out


STORED_DOSSIER_SCHEMA = _with_figure_data(DOSSIER_SCHEMA)

PLAIN_SCHEMA: dict[str, Any] = {
    **DOSSIER_SCHEMA,
    "properties": {**DOSSIER_SCHEMA["properties"], "figure_texts": _arr(S)},
    "required": [*DOSSIER_SCHEMA["required"], "figure_texts"],
}


class ShapeMismatch(ValueError):
    pass


def _get_all(doc: Any, parts: list[str]) -> list[tuple[list, str | int]]:
    """Return (container, key) pairs for every value at the path.

    A null or missing value on the path has no values under it, e.g., a figure
    without data, or figure data from a template without steps.
    """
    if doc is None:
        return []
    head, rest = parts[0], parts[1:]
    if head.endswith("[]"):
        name = head[:-2]
        lst = doc.get(name) if name else doc
        if lst is None:
            return []
        if not rest:
            return [(lst, i) for i in range(len(lst))]
        out = []
        for item in lst:
            out += _get_all(item, rest)
        return out
    if not rest:
        return [(doc, head)]
    return _get_all(doc.get(head), rest)


def rewrite_input(dossier: dict) -> dict:
    """Return the input of the plain-writing call, in the shape of PLAIN_SCHEMA.

    The input has no links and no figure data. The text of every figure step
    is in "figure_texts" instead, in the order of FIGURE_TEXTS.
    """
    out = without_links(dossier)
    out["figures"] = [{k: v for k, v in f.items() if k != "data"} for f in dossier["figures"]]
    out["figure_texts"] = [c[k] for c, k in _get_all(dossier, FIGURE_TEXTS.split("."))]
    return out


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
        if path == FIGURE_TEXTS:
            texts = rewritten.get("figure_texts") or []
            src = [(texts, i) for i in range(len(texts))]
        else:
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
    objects with required keys and no other keys, arrays, strings, numbers,
    integers, booleans, null, enums, and anyOf. The server uses it on dossiers
    from export files, because those dossiers didn't come from a call with
    structured output.
    """
    where = path or "the dossier"
    if "anyOf" in schema:
        subs = schema["anyOf"]
        if value is None and any(sub.get("type") == "null" for sub in subs):
            return None
        subs = [sub for sub in subs if sub.get("type") != "null"]
        if len(subs) == 1:
            return shape_problem(value, subs[0], path)
        # Figure data names its template, so the server checks the data
        # against that template and reports the problem with it.
        if isinstance(value, dict):
            named = [sub for sub in subs if value.get("template") in sub.get("properties", {}).get("template", {}).get("enum", [])]
            if named:
                return shape_problem(value, named[0], path)
        if all(shape_problem(value, sub, path) for sub in subs):
            return f"{where} doesn't match any of the allowed shapes"
        return None
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
    if t == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        return f"{where} must be a number"
    if t == "null" and value is not None:
        return f"{where} must be null"
    if "enum" in schema and value not in schema["enum"]:
        return f"{where} must be one of {', '.join(schema['enum'])}"
    return None


# Limits that keep a figure readable on a phone. A figure over a limit has
# its data set to null.
FIGURE_LIMITS = {"metrics": 8, "methods": 12, "inputs": 6, "outputs": 6, "choices": 24, "phases": 12, "steps": 16, "details": 8, "thresholds": 24, "items": 40}
MAX_POWER = 4


def figure_data_problem(data: dict) -> str | None:
    """Return why the page couldn't draw the figure data, or None."""
    t = data["template"]

    def finite(*values: Any) -> bool:
        return all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)

    def sized(name: str, items: list, least: int = 1) -> str | None:
        if len(items) < least:
            return f"it needs at least {least} {name}"
        if len(items) > FIGURE_LIMITS[name]:
            return f"it has more than {FIGURE_LIMITS[name]} {name}"
        return None

    if t == "comparison":
        problem = sized("metrics", data["metrics"]) or sized("methods", data["methods"], 2)
        if problem:
            return problem
        for m in data["methods"]:
            if len(m["values"]) != len(data["metrics"]):
                return f"{m['name']!r} doesn't have one value for each metric"
            if not finite(*(v for v in m["values"] if v is not None)):
                return "a value isn't a finite number"
    elif t == "calculator":
        problem = sized("inputs", data["inputs"]) or sized("outputs", data["outputs"])
        if problem:
            return problem
        for i in data["inputs"]:
            problem = sized("choices", i["choices"])
            if problem:
                return problem
            if not finite(*i["choices"]) or not 0 <= i["default_index"] < len(i["choices"]):
                return f"the input {i['name']!r} has a bad choice or default"
        for o in data["outputs"]:
            if len(o["powers"]) != len(data["inputs"]):
                return f"the output {o['name']!r} doesn't have one power for each input"
            if not finite(o["constant"], *o["powers"]) or any(abs(p) > MAX_POWER for p in o["powers"]):
                return f"the output {o['name']!r} has a bad constant or power"
    elif t == "timeline":
        problem = sized("phases", data["phases"])
        if problem:
            return problem
        for p in data["phases"]:
            if not finite(p["start"], p["end"], p["start_value"], p["end_value"]) or p["end"] <= p["start"]:
                return f"the phase {p['label']!r} has bad numbers"
    elif t == "steps":
        problem = sized("steps", data["steps"], 2)
        if problem:
            return problem
        for st in data["steps"]:
            if sized("details", st["details"], 0) or (st["value"] is not None and not finite(st["value"])):
                return f"the step {st['label']!r} has too many details or a bad value"
    elif t == "threshold":
        problem = sized("thresholds", data["thresholds"]) or sized("items", data["items"], 2)
        if problem:
            return problem
        if not finite(*data["thresholds"], *(i["score"] for i in data["items"])) or not 0 <= data["default_index"] < len(data["thresholds"]):
            return "a threshold, a score, or the default isn't valid"
    return None


def apply_figure_data(dossier: dict, result: dict) -> dict:
    """Add the data from the figures call to a copy of the dossier, and clean it.

    An item with a figure index that isn't in the dossier is dropped, and
    each figure keeps only its first item. A figure without an item gets no
    data.
    """
    import copy

    out = copy.deepcopy(dossier)
    figures = out["figures"]
    for f in figures:
        f["data"] = None
    for name in FIGURE_FIELDS:
        for item in result.get(name) or []:
            i = item.get("figure")
            if not (isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(figures)) or figures[i]["data"] is not None:
                continue
            figures[i]["data"] = _stored_data(name, item)
            if item.get("made_up_values"):
                figures[i]["uses_made_up_values"] = True
    return clean_figures(out)


def clean_figures(dossier: dict) -> dict:
    """Return a copy of the dossier where every figure has a "data" field the page can draw, or null."""
    import copy

    out = copy.deepcopy(dossier)
    for f in out["figures"]:
        data = f.get("data")
        f["data"] = data if data is not None and figure_data_problem(data) is None else None
    return out
