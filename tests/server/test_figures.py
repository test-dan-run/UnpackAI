import copy

import pytest
from fastapi.testclient import TestClient

from conftest import DRAFT
from unpackai_server.app import create_app
from unpackai_server.dossier_schema import DOSSIER_SCHEMA, clean_figures, figure_data_problem, shape_problem


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


def change(data, fn):
    data = copy.deepcopy(data)
    fn(data)
    return data


@pytest.mark.parametrize("data", [CALCULATOR, TIMELINE, THRESHOLD, DRAFT["figures"][0]["data"], DRAFT["figures"][1]["data"]])
def test_each_template_matches_the_schema_and_can_be_drawn(data):
    dossier = {**DRAFT, "figures": [figure(data)]}
    assert shape_problem(dossier, DOSSIER_SCHEMA) is None
    assert figure_data_problem(data) is None


@pytest.mark.parametrize("data, problem", [
    (change(DRAFT["figures"][1]["data"], lambda d: d["methods"][1]["values"].append(3)), "one value for each metric"),
    (change(DRAFT["figures"][1]["data"], lambda d: d["methods"].pop()), "at least 2 methods"),
    (change(DRAFT["figures"][1]["data"], lambda d: d["methods"][0].update(values=[float("nan")])), "finite"),
    (change(CALCULATOR, lambda d: d["outputs"][0].update(powers=[1, 9])), "bad constant or power"),
    (change(CALCULATOR, lambda d: d["outputs"][0].update(powers=[1])), "one power for each input"),
    (change(CALCULATOR, lambda d: d["inputs"][1].update(default_index=2)), "bad choice or default"),
    (change(CALCULATOR, lambda d: d["inputs"][0].update(choices=[])), "at least 1 choices"),
    (change(TIMELINE, lambda d: d["phases"][1].update(end=1)), "bad numbers"),
    (change(THRESHOLD, lambda d: d.update(default_index=-1)), "isn't valid"),
    (change(THRESHOLD, lambda d: d.update(items=[{"label": str(i), "score": i} for i in range(41)])), "more than 40 items"),
    (change(DRAFT["figures"][0]["data"], lambda d: d["steps"].pop()), "at least 2 steps"),
])
def test_figure_data_the_page_cant_draw_is_found(data, problem):
    assert problem in figure_data_problem(data)
    assert clean_figures({"figures": [figure(data)]})["figures"][0]["data"] is None


def test_figure_data_goes_through_the_rewrite_and_is_stored(client, fake_api):
    bad = change(CALCULATOR, lambda d: d["outputs"][0].update(powers=[1, 9]))
    fake_api.draft = {**DRAFT, "figures": DRAFT["figures"] + [figure(bad, "Broken"), figure(None, "No template")]}
    pid = client.post("/api/unpack", json={"url": "2312.00752"}).json()["paper_id"]
    paper = client.get(f"/api/papers/{pid}").json()
    assert paper["status"] == "done", paper["error"]
    figures = paper["dossier"]["content"]["figures"]
    steps = figures[0]["data"]["steps"]
    # The rewrite changed the text of a step, and the server kept the number
    # that the rewrite tried to change.
    assert steps[0]["text"] == "The first step uses fast memory."
    assert steps[1]["value"] == 2048
    assert figures[1]["data"]["methods"][0]["values"] == [5]
    # The broken calculator was set to null before the rewrite, so the page
    # shows only its title and note.
    assert figures[2]["data"] is None and figures[3]["data"] is None
    assert not {p["field"] for p in paper["dossier"]["text_problems"]} & {"figures[].data.steps[].text#0"}


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
