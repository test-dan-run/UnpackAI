import copy
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from conftest import DRAFT, S4_DRAFT
from unpackai_server import app as app_module
from unpackai_server.app import create_app
from unpackai_server.db import Database


@pytest.fixture
def client(unpacker, stored_key):
    with TestClient(create_app(unpacker=unpacker)) as c:
        yield c


@pytest.fixture
def other(tmp_path):
    """A second library with its own database, which never calls Claude."""
    with TestClient(create_app(db_path=tmp_path / "other.sqlite3")) as c:
        yield c


def unpack_two_papers(client, fake_api):
    """Unpack S4 and then Mamba, with a link from a Mamba idea to an S4 idea."""
    fake_api.draft = S4_DRAFT
    s4 = client.post("/api/unpack", json={"url": "2111.00396"}).json()["paper_id"]
    fake_api.draft = DRAFT
    fake_api.links = [{"novelty": 0, "earlier_paper": s4, "earlier_novelty": 0, "relation": "builds_on"}]
    mamba = client.post("/api/unpack", json={"url": "2312.00752"}).json()["paper_id"]
    return s4, mamba


def test_export_and_import_move_dossiers_between_libraries(client, other, fake_api):
    s4, mamba = unpack_two_papers(client, fake_api)
    # A paper whose unpack failed isn't in the export.
    fake_api.extract_stop = "refusal"
    client.post("/api/unpack", json={"url": "https://example.com/blog/post"})

    r = client.get("/api/export")
    assert r.status_code == 200
    assert r.headers["content-disposition"] == 'attachment; filename="unpackai-library.json"'
    data = r.json()
    assert data["format"] == "unpackai-export" and data["version"] == 2
    assert [p["source"] for p in data["papers"]] == ["arxiv:2111.00396", "arxiv:2312.00752"]
    # The file names the earlier paper by its source, because ids differ
    # between libraries, and it holds no calls, raw output, or text problems.
    link = data["papers"][1]["dossier"]["novelties"][0]["earlier"]
    assert link == {"source": "arxiv:2111.00396", "title": S4_DRAFT["paper"]["title"], "published": "Nov 2021", "idea": "Structured state space layer", "relation": "builds_on"}
    assert set(data["papers"][0]) == {"source", "source_kind", "dossier"}

    # The other library already has a paper, so the ids of the imported papers differ.
    other.app.state.db.upsert_paper("text:0123456789abcdef", "text")
    r = other.post("/api/import", content=json.dumps(data), headers={"content-type": "application/json"})
    assert r.status_code == 200, r.text
    added = r.json()["added"]
    assert [a["source"] for a in added] == ["arxiv:2111.00396", "arxiv:2312.00752"] and r.json()["skipped"] == []
    new_s4, new_mamba = added[0]["paper_id"], added[1]["paper_id"]
    assert (new_s4, new_mamba) != (s4, mamba)

    paper = other.get(f"/api/papers/{new_mamba}").json()
    assert paper["status"] == "done" and paper["title"] == DRAFT["paper"]["title"] and paper["paper_type"] == "model"
    assert paper["dossier"]["origin"] == "import" and paper["dossier"]["version"] == 1
    assert paper["dossier"]["content"]["novelties"][0]["earlier"]["paper_id"] == new_s4
    assert paper["dossier"]["content"]["thesis"] == client.get(f"/api/papers/{mamba}").json()["dossier"]["content"]["thesis"]
    later = other.get(f"/api/papers/{new_s4}").json()["later"]
    assert [(x["paper_id"], x["idea"]) for x in later] == [(new_mamba, "Selection mechanism")]
    # The dossiers from the first library were unpacked there.
    assert client.get(f"/api/papers/{mamba}").json()["dossier"]["origin"] == "unpack"

    # A second import of the same file skips both papers.
    again = other.post("/api/import", json=data).json()
    assert again["added"] == [] and [s["paper_id"] for s in again["skipped"]] == [new_s4, new_mamba]


def test_one_paper_export_keeps_a_link_to_a_missing_paper_without_an_id(client, other, fake_api):
    s4, mamba = unpack_two_papers(client, fake_api)
    assert client.get("/api/papers/999/export").status_code == 404
    fake_api.extract_stop = "refusal"
    failed = client.post("/api/unpack", json={"url": "https://example.com/blog/post"}).json()["paper_id"]
    assert client.get(f"/api/papers/{failed}/export").status_code == 409

    r = client.get(f"/api/papers/{mamba}/export")
    assert r.headers["content-disposition"] == f'attachment; filename="unpackai-paper-{mamba}.json"'
    data = r.json()
    assert [p["source"] for p in data["papers"]] == ["arxiv:2312.00752"]

    added = other.post("/api/import", json=data).json()["added"]
    link = other.get(f"/api/papers/{added[0]['paper_id']}").json()["dossier"]["content"]["novelties"][0]["earlier"]
    assert link["paper_id"] is None and link["title"] == S4_DRAFT["paper"]["title"]

    # An export of that paper from the second library still has the title.
    again = other.get(f"/api/papers/{added[0]['paper_id']}/export").json()
    assert again["papers"][0]["dossier"]["novelties"][0]["earlier"]["source"] is None


def test_import_replaces_a_failed_unpack_of_the_same_source(client, other, fake_api):
    _, mamba = unpack_two_papers(client, fake_api)
    data = client.get(f"/api/papers/{mamba}/export").json()
    db: Database = other.app.state.db
    pid, _ = db.upsert_paper("arxiv:2312.00752", "arxiv")
    db.set_status(pid, "failed", "Claude API error 401")

    r = other.post("/api/import", json=data).json()
    assert [a["paper_id"] for a in r["added"]] == [pid]
    paper = other.get(f"/api/papers/{pid}").json()
    assert paper["status"] == "done" and paper["error"] is None and paper["dossier"]["origin"] == "import"


def bad(change):
    def make(data):
        data = copy.deepcopy(data)
        change(data)
        return data
    return make


@pytest.mark.parametrize("make, problem", [
    (bad(lambda d: d.update(format="something-else")), "isn't an UnpackAI export file"),
    (bad(lambda d: d.update(version=3)), "reads versions 1 to 2"),
    (bad(lambda d: d["papers"][0]["dossier"]["figures"][0]["data"].update(template="pie")), "doesn't match any of the allowed shapes"),
    (bad(lambda d: d["papers"][0]["dossier"]["figures"][0]["data"]["steps"][0].update(value="<b>")), "steps[0].value"),
    (bad(lambda d: d.pop("papers")), "no list of papers"),
    (bad(lambda d: d["papers"][1]["dossier"].pop("thesis")), "Paper 2 in the file has a problem"),
    (bad(lambda d: d["papers"][0]["dossier"].update(script="<script>")), "unknown field 'script'"),
    (bad(lambda d: d["papers"][0]["dossier"]["novelties"][0].update(status="best")), "novelties[0].status must be one of"),
    (bad(lambda d: d["papers"][0]["dossier"]["specs"].append({"value": 5, "label": "x"})), "specs[1].value must be a string"),
    (bad(lambda d: d["papers"][0]["dossier"]["paper"].update(source_url="javascript:alert(1)")), "source_url must start with http"),
    (bad(lambda d: d["papers"][0].update(source="arxiv:../../etc")), "isn't a valid arxiv source"),
    (bad(lambda d: d["papers"][0].update(source_kind="ftp")), "source_kind must be one of"),
    (bad(lambda d: d["papers"][1]["dossier"]["novelties"][0]["earlier"].update(relation="copies")), "relation must be one of"),
    (bad(lambda d: d["papers"][1]["dossier"]["novelties"][0]["earlier"].update(paper_id=1)), "must have the fields"),
])
def test_import_rejects_a_bad_file_and_stores_nothing(client, other, fake_api, make, problem):
    unpack_two_papers(client, fake_api)
    data = make(client.get("/api/export").json())
    r = other.post("/api/import", json=data)
    assert r.status_code == 400 and problem in r.json()["detail"], r.json()
    # The server stores no paper from the file, including the papers that had no problem.
    assert other.get("/api/papers").json() == []


def test_import_rejects_a_file_that_isnt_json_or_is_too_large(other, monkeypatch):
    r = other.post("/api/import", content=b"not json", headers={"content-type": "application/json"})
    assert r.status_code == 400 and "isn't valid JSON" in r.json()["detail"]
    monkeypatch.setattr(app_module, "MAX_BYTES", 100)
    r = other.post("/api/import", content=b"x" * 101)
    assert r.status_code == 413
    assert other.get("/api/papers").json() == []


def test_a_database_from_before_the_origin_column_gets_it(tmp_path):
    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE dossiers (id INTEGER PRIMARY KEY, paper_id INTEGER NOT NULL, version INTEGER NOT NULL, "
        "content TEXT NOT NULL, text_problems TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE (paper_id, version));"
        "INSERT INTO dossiers VALUES (1, 7, 1, '{}', '[]', '2026-11-01T00:00:00+00:00');"
    )
    conn.commit()
    conn.close()
    assert Database(path).latest_dossier(7)["origin"] == "unpack"
