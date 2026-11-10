import copy

import pytest
from fastapi.testclient import TestClient

import json

from conftest import DRAFT, FIGURE_RESULT
from unpackai_server.app import create_app
from unpackai_server.dossier_schema import (
    COMPARE_SCHEMA,
    DOSSIER_SCHEMA,
    FIGURES_SCHEMA,
    PLAIN_SCHEMA,
    STORED_DOSSIER_SCHEMA,
    apply_figure_data,
    clean_figures,
    figure_data_problem,
    shape_problem,
)


@pytest.fixture
def client(unpacker, stored_key):
    with TestClient(create_app(unpacker=unpacker)) as c:
        yield c


def figure(data, title="Figure"):
    return {"tab": "overview", "kind": "other", "title": title, "what_to_notice": "Look at the bars.", "uses_made_up_values": False, "data": data}


CALCULATOR = {
    "template": "calculator", "source": "Section 2.1",
    "inputs": [
        {"name": "Layers", "unit": "", "choices": [61], "default_index": 0, "from_paper": True},
        {"name": "Context", "unit": "tokens", "choices": [4096, 131072], "default_index": 1, "from_paper": True},
    ],
    "outputs": [{"name": "MLA cache", "unit": "bytes", "constant": 1152, "powers": [1, 1]}],
}
TIMELINE = {
    "template": "timeline", "source": "Section 4.2", "x_name": "Tokens", "x_unit": "T", "y_name": "Learning rate", "y_unit": "",
    "phases": [{"label": "Warmup", "start": 0, "end": 2, "start_value": 0, "end_value": 2.2e-4, "shape": "linear"},
               {"label": "Decay", "start": 2, "end": 14.8, "start_value": 2.2e-4, "end_value": 2.2e-5, "shape": "cosine"}],
}
THRESHOLD = {
    "template": "threshold", "source": "Section 3.4", "score_name": "Educational score", "keep_when": "at_least",
    "thresholds": [2, 3, 4], "default_index": 1, "items": [{"label": "A tutorial", "score": 4.1}, {"label": "An ad", "score": 0.5}],
}


# The stored data of the two figures in DRAFT, after apply_figure_data().
STEPS = apply_figure_data(DRAFT, FIGURE_RESULT)["figures"][0]["data"]
COMPARISON = apply_figure_data(DRAFT, FIGURE_RESULT)["figures"][1]["data"]


def change(data, fn):
    data = copy.deepcopy(data)
    fn(data)
    return data


@pytest.mark.parametrize("data", [CALCULATOR, TIMELINE, THRESHOLD, STEPS, COMPARISON])
def test_each_template_matches_the_schema_and_can_be_drawn(data):
    dossier = {**DRAFT, "figures": [figure(data)]}
    assert shape_problem(dossier, STORED_DOSSIER_SCHEMA) is None
    assert figure_data_problem(data) is None


@pytest.mark.parametrize("data, problem", [
    (change(COMPARISON, lambda d: d["methods"][1]["values"].append(3)), "one value for each metric"),
    (change(COMPARISON, lambda d: d["methods"].pop()), "at least 2 methods"),
    (change(COMPARISON, lambda d: d["methods"][0].update(values=[float("nan")])), "finite"),
    (change(CALCULATOR, lambda d: d["outputs"][0].update(powers=[1, 9])), "bad constant or power"),
    (change(CALCULATOR, lambda d: d["outputs"][0].update(powers=[1])), "one power for each input"),
    (change(CALCULATOR, lambda d: d["inputs"][1].update(default_index=2)), "bad choice or default"),
    (change(CALCULATOR, lambda d: d["inputs"][0].update(choices=[])), "at least 1 choices"),
    (change(TIMELINE, lambda d: d["phases"][1].update(end=1)), "bad numbers"),
    (change(THRESHOLD, lambda d: d.update(default_index=-1)), "isn't valid"),
    (change(THRESHOLD, lambda d: d.update(items=[{"label": str(i), "score": i} for i in range(41)])), "more than 40 items"),
    (change(STEPS, lambda d: d["steps"].pop()), "at least 2 steps"),
])
def test_figure_data_the_page_cant_draw_is_found(data, problem):
    assert problem in figure_data_problem(data)
    assert clean_figures({"figures": [figure(data)]})["figures"][0]["data"] is None


def test_schemas_sent_to_claude_have_no_union_types():
    # The API compiles each output schema into a grammar, and union types
    # make the grammar grow fast. The dossier schema with the figure
    # templates in it was rejected as too large.
    for schema in (DOSSIER_SCHEMA, PLAIN_SCHEMA, FIGURES_SCHEMA, COMPARE_SCHEMA):
        text = json.dumps(schema)
        assert "anyOf" not in text and '"null"' not in text
    assert "template" not in json.dumps(DOSSIER_SCHEMA) and "template" not in json.dumps(PLAIN_SCHEMA)


def test_the_figures_call_fills_the_figures_and_the_rewrite_gets_their_text(client, fake_api):
    bad = {"figure": 2, "made_up_values": False, "source": "Section 2", "inputs": CALCULATOR["inputs"],
           "outputs": [{"name": "Cache", "unit": "bytes", "constant": 2, "powers": [1, 9]}]}
    fake_api.draft = {**DRAFT, "figures": DRAFT["figures"] + [figure(None, "Broken"), figure(None, "No template")]}
    for f in fake_api.draft["figures"]:
        f.pop("data", None)
    fake_api.figure_result = {
        **FIGURE_RESULT,
        "calculator": [bad],
        # An unknown index is dropped, and so is a second template for figure 1.
        "timeline": [{**{k: v for k, v in TIMELINE.items() if k != "template"}, "figure": 99, "made_up_values": False},
                     {**{k: v for k, v in TIMELINE.items() if k != "template"}, "figure": 1, "made_up_values": False}],
    }
    pid = client.post("/api/unpack", json={"url": "2312.00752"}).json()["paper_id"]
    paper = client.get(f"/api/papers/{pid}").json()
    assert paper["status"] == "done", paper["error"]
    figures = paper["dossier"]["content"]["figures"]
    assert [f["data"] and f["data"]["template"] for f in figures] == ["steps", "comparison", None, None]
    steps = figures[0]["data"]["steps"]
    # The step without a value has a null value, and the made-up values flag
    # from the figures call reached the figure.
    assert steps[0]["value"] is None and steps[1]["value"] == 2048 and figures[0]["uses_made_up_values"] is True
    assert figures[1]["data"]["methods"][0]["values"] == [5]
    # The rewrite changed the text of a step. The text check found nothing in it.
    assert steps[0]["text"] == "The first step uses fast memory."
    assert not {p["field"] for p in paper["dossier"]["text_problems"]} & {"figures[].data.steps[].text#0"}

    # The figures call got the figure plan, and the rewrite got the step
    # texts as a flat list without the figure data.
    figures_call = next(r["body"] for r in fake_api.requests if r["body"]["system"][0]["text"].startswith("You fill in the numbers"))
    assert '"figure": 3' in figures_call["messages"][0]["content"][-1]["text"]
    assert figures_call["messages"][0]["content"][0]["source"]["url"] == "https://arxiv.org/pdf/2312.00752"
    rewrite_input = json.loads(fake_api.requests[-1]["body"]["messages"][0]["content"])
    assert rewrite_input["figure_texts"] == ["This step leverages fast memory.", "The scan reads each token once."]
    assert all("data" not in f for f in rewrite_input["figures"])


def test_a_dossier_without_figures_skips_the_figures_call(client, fake_api):
    fake_api.draft = {**DRAFT, "figures": []}
    pid = client.post("/api/unpack", json={"url": "2312.00752"}).json()["paper_id"]
    assert [c["step"] for c in client.get(f"/api/papers/{pid}").json()["calls"]] == ["extract", "plain_writing"]


def test_dossiers_from_before_figure_data_still_export_and_import(client, fake_api, tmp_path):
    pid = client.post("/api/unpack", json={"url": "2312.00752"}).json()["paper_id"]
    db = client.app.state.db
    old = copy.deepcopy(db.latest_dossier(pid)["content"])
    for f in old["figures"]:
        del f["data"]
    db.add_dossier(pid, old, [])
    data = client.get("/api/export").json()
    assert [f["data"] for f in data["papers"][0]["dossier"]["figures"]] == [None, None]

    # A version 1 file has no data field in its figures.
    data["version"] = 1
    for f in data["papers"][0]["dossier"]["figures"]:
        del f["data"]
    with TestClient(create_app(db_path=tmp_path / "other.sqlite3")) as other:
        r = other.post("/api/import", json=data)
        assert r.status_code == 200, r.text
        stored = other.get(f"/api/papers/{r.json()['added'][0]['paper_id']}").json()["dossier"]["content"]
    assert [f["data"] for f in stored["figures"]] == [None, None]


def test_schema_check_finds_the_part_the_api_rejects(unpacker, stored_key, fake_api):
    fake_api.reject_schema = lambda schema: "figures" in schema["properties"]
    results = dict(unpacker.check_schemas())
    assert results["figures"] == results["compare"] == "accepted"
    assert "grammar is too large" in results["extract"] and "grammar is too large" in results["plain_writing"]
    assert "grammar is too large" in results["extract.figures"] and results["extract.thesis"] == "accepted"
    # Each request asks for at most 64 output tokens.
    assert {r["body"]["max_tokens"] for r in fake_api.requests} == {64}
