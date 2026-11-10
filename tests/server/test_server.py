import json
import logging

import pytest
from fastapi.testclient import TestClient

from conftest import DRAFT, FAKE_KEY
from unpackai_server.app import create_app
from unpackai_server.db import Database
from unpackai_server.safe_logging import REDACTOR
from unpackai_server.unpack import parse_source


@pytest.fixture
def client(unpacker, stored_key):
    with TestClient(create_app(unpacker=unpacker)) as c:
        yield c


def test_parse_source():
    assert parse_source("https://arxiv.org/abs/2312.00752v2").key == "arxiv:2312.00752"
    assert parse_source("2312.00752").url == "https://arxiv.org/pdf/2312.00752"
    assert parse_source("https://arxiv.org/abs/2312.00752?context=cs#S4").key == "arxiv:2312.00752"
    assert parse_source("https://example.com/paper.pdf").kind == "pdf_url"
    assert parse_source("https://example.com/blog/post").kind == "web_url"
    assert parse_source(text="Full text").kind == "text"


def test_unpack_stores_every_generated_item(client, fake_api):
    r = client.post("/api/unpack", json={"url": "https://arxiv.org/abs/2312.00752"})
    assert r.status_code == 202
    pid = r.json()["paper_id"]

    paper = client.get(f"/api/papers/{pid}").json()
    assert paper["status"] == "done", paper["error"]
    assert paper["title"].startswith("Mamba")

    gens = client.get(f"/api/papers/{pid}/generations").json()
    assert [g["step"] for g in gens] == ["extract", "plain_writing"]
    assert all(g["request_id"] == "req_test" and g["output"] for g in gens)

    d = paper["dossier"]["content"]
    assert d["thesis"].endswith("instead of attention.")
    assert d["novelties"][0]["why"] == "The parameters depend on the input."
    # The rewrite tried to change a status and a number. Both are kept.
    assert d["novelties"][0]["status"] == "novel"
    assert d["specs"][0]["value"] == "5x"
    assert d["highlights"] == ["selective state spaces"]
    # The draft's dash, "This tab", and "leverages" were rewritten, so the
    # text checker finds no problems in those fields.
    problems = {p["field"] for p in paper["dossier"]["text_problems"]}
    assert not problems & {"thesis#0", "tabs[].lede#0", "novelties[].why#0"}

    # The PDF goes to Claude as a URL document block.
    first = fake_api.requests[0]["body"]
    assert first["messages"][0]["content"][0]["source"] == {"type": "url", "url": "https://arxiv.org/pdf/2312.00752"}
    assert first["fallbacks"] == "default"

    # A second request for the same paper doesn't call Claude again.
    again = client.post("/api/unpack", json={"url": "2312.00752"}).json()
    assert again == {**again, "paper_id": pid, "queued": False}
    assert len(fake_api.requests) == 2


def test_key_comes_from_docker_secret_and_never_reaches_logs_or_responses(unpacker, stored_key, fake_api, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_LOG", "debug")
    app = create_app(unpacker=unpacker)

    # A plain handler without the redaction filter, at DEBUG, so the test
    # sees everything the libraries and the server emit.
    captured = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            captured.append(self.format(record))

    root = logging.getLogger()
    handler = ListHandler(level=logging.DEBUG)
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        with TestClient(app) as c:
            pid = c.post("/api/unpack", json={"url": "https://arxiv.org/abs/2312.00752"}).json()["paper_id"]
            bodies = [c.get(u).text for u in ("/api/health", "/api/papers", f"/api/papers/{pid}", f"/api/papers/{pid}/generations")]
    finally:
        root.removeHandler(handler)

    # The SDK sent the key from the Docker secret to the API. SDK 2.x sends an API
    # key as "Authorization: Bearer", and older releases used "x-api-key".
    sent = fake_api.requests[0]["headers"]
    assert sent.get("authorization") == f"Bearer {FAKE_KEY}" or sent.get("x-api-key") == FAKE_KEY
    log_text = "\n".join(captured)
    assert "POST /api/unpack 202" in log_text
    assert FAKE_KEY not in log_text
    assert "x-api-key" not in log_text.lower()
    assert "authorization" not in log_text.lower()
    assert "Request options" not in log_text
    for body in bodies:
        assert FAKE_KEY not in body
    assert json.loads(bodies[0]) == {"ok": True, "api_key_configured": True}


def test_redaction_filter_catches_headers_if_a_library_logs_them():
    REDACTOR.add_secret(FAKE_KEY)
    for line in (
        f"headers={{'x-api-key': '{FAKE_KEY}', 'accept': 'application/json'}}",
        f"[(b'x-api-key', b'{FAKE_KEY}')]",
        "Authorization: Bearer abc.def.ghi",
        f"something {FAKE_KEY} something",
        "sk-ant-api03-ABCDEFGHIJKLMNOP",
    ):
        clean = REDACTOR.redact(line)
        assert FAKE_KEY not in clean and "abc.def.ghi" not in clean and "ABCDEFGHIJKLMNOP" not in clean, clean


def test_missing_key_fails_the_unpack_with_a_clear_message(unpacker, fake_api):
    with TestClient(create_app(unpacker=unpacker)) as c:
        assert c.get("/api/health").json()["api_key_configured"] is False
        pid = c.post("/api/unpack", json={"url": "2312.00752"}).json()["paper_id"]
        paper = c.get(f"/api/papers/{pid}").json()
    assert paper["status"] == "failed"
    assert "scripts/compose-up.sh" in paper["error"]
    assert fake_api.requests == []


def test_refusal_is_stored_and_the_failed_paper_can_be_retried(client, fake_api):
    fake_api.extract_stop = "refusal"
    pid = client.post("/api/unpack", json={"url": "2312.00752"}).json()["paper_id"]
    paper = client.get(f"/api/papers/{pid}").json()
    assert paper["status"] == "failed" and "declined" in paper["error"]
    assert paper["step"] == "extract"
    gens = client.get(f"/api/papers/{pid}/generations").json()
    assert gens[0]["stop_reason"] == "refusal" and gens[0]["error"]

    fake_api.extract_stop = "end_turn"
    assert client.post("/api/unpack", json={"url": "2312.00752"}).json()["queued"] is True
    assert client.get(f"/api/papers/{pid}").json()["status"] == "done"


def test_rewrite_that_changes_list_lengths_is_rejected(client, fake_api):
    def bad(d):
        d = json.loads(json.dumps(d))
        d["claims"] = []
        return d

    fake_api.rewrite_fn = bad
    pid = client.post("/api/unpack", json={"url": "2312.00752"}).json()["paper_id"]
    paper = client.get(f"/api/papers/{pid}").json()
    assert paper["status"] == "failed" and "changed the shape" in paper["error"]
    assert paper["step"] == "plain_writing"
    assert paper["dossier"] is None


def test_bad_source_is_a_400(client):
    assert client.post("/api/unpack", json={"url": "ftp://x"}).status_code == 400
    assert client.post("/api/unpack", json={}).status_code == 400


def test_unfinished_papers_are_marked_failed_on_restart(unpacker):
    db = unpacker.db
    pid, _ = db.upsert_paper("arxiv:1", "arxiv")
    db.set_status(pid, "running")
    with TestClient(create_app(unpacker=unpacker)) as c:
        assert c.get(f"/api/papers/{pid}").json()["status"] == "failed"


def test_dossier_versions_increase(tmp_path):
    db = Database(tmp_path / "v.sqlite3")
    pid, _ = db.upsert_paper("text:abc", "text")
    assert db.add_dossier(pid, DRAFT, []) == 1
    assert db.add_dossier(pid, DRAFT, []) == 2
    assert db.latest_dossier(pid)["version"] == 2


def test_secret_written_after_start_is_read_on_the_next_unpack(unpacker, fake_api, secret_file):
    with TestClient(create_app(unpacker=unpacker)) as c:
        pid = c.post("/api/unpack", json={"url": "2312.00752"}).json()["paper_id"]
        assert c.get(f"/api/papers/{pid}").json()["status"] == "failed"

        secret_file.write_text(FAKE_KEY + "\n")
        assert c.get("/api/health").json()["api_key_configured"] is True
        assert c.post("/api/unpack", json={"url": "2312.00752"}).json()["queued"] is True
        assert c.get(f"/api/papers/{pid}").json()["status"] == "done"
    assert fake_api.requests[0]["headers"]["authorization"] == f"Bearer {FAKE_KEY}"


def test_paper_lists_its_calls_without_the_raw_output(client):
    pid = client.post("/api/unpack", json={"url": "2312.00752"}).json()["paper_id"]
    calls = client.get(f"/api/papers/{pid}").json()["calls"]
    assert [c["step"] for c in calls] == ["extract", "plain_writing"]
    assert all("output" not in c and c["model"] == "claude-opus-5-5" for c in calls)


def test_retry_starts_a_failed_unpack_again(client, fake_api):
    fake_api.extract_stop = "refusal"
    pid = client.post("/api/unpack", json={"url": "https://arxiv.org/abs/2312.00752?context=cs"}).json()["paper_id"]
    assert client.get(f"/api/papers/{pid}").json()["status"] == "failed"

    fake_api.extract_stop = "end_turn"
    r = client.post(f"/api/papers/{pid}/retry")
    assert r.status_code == 202
    assert client.get(f"/api/papers/{pid}").json()["status"] == "done"
    # The retry sends the same PDF URL as the first unpack.
    extracts = [req["body"] for req in fake_api.requests if "<unpack_skill>" in req["body"]["system"][0]["text"]]
    urls = [body["messages"][0]["content"][0]["source"]["url"] for body in extracts]
    assert urls == ["https://arxiv.org/pdf/2312.00752"] * 2

    # A paper that isn't failed, a missing paper, and pasted text can't be retried.
    assert client.post(f"/api/papers/{pid}/retry").status_code == 409
    assert client.post("/api/papers/999/retry").status_code == 404
    fake_api.extract_stop = "refusal"
    tid = client.post("/api/unpack", json={"text": "Full text of a paper"}).json()["paper_id"]
    r = client.post(f"/api/papers/{tid}/retry")
    assert r.status_code == 400 and "send the text again" in r.json()["detail"]
