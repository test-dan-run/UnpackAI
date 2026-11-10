import copy
import json
import sys
from pathlib import Path

import anthropic
import httpx2
import pytest

# tests/server/conftest.py, so the server package is in src/server.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "server"))

from unpackai_server.db import Database  # noqa: E402
from unpackai_server.unpack import Unpacker  # noqa: E402

FAKE_KEY = "sk-ant-test-0123456789abcdefghijklmnop"

DRAFT = {
    "paper": {
        "title": "Mamba: Linear-Time Sequence Modeling with Selective State Spaces",
        "org": "CMU and Princeton",
        "published": "Dec 2023",
        "source_url": "https://arxiv.org/pdf/2312.00752",
        "paper_type": "model",
    },
    "thesis": "Mamba is a sequence model that uses selective state spaces — it drops attention.",
    "highlights": ["selective state spaces"],
    "specs": [{"value": "5x", "label": "higher inference throughput than Transformers"}],
    "tabs": [
        {"id": "overview", "title": "Overview", "lede": "This tab lists the new ideas."},
        {"id": "evidence", "title": "Evidence", "lede": "Claims and their support."},
    ],
    "novelties": [
        {"what": "Selection mechanism", "status": "novel", "replaces": "Fixed SSM parameters", "why": "It leverages input-dependent parameters.", "where": "overview"}
    ],
    "claims": [
        {"heading": "Linear scaling", "text": "Mamba scales linearly in sequence length.", "evidence": "Benchmark", "evidence_class": "ok", "where": "evidence"}
    ],
    "figures": [
        {"tab": "overview", "kind": "block_loop_animation", "title": "Scan", "what_to_notice": "The scan runs once.", "uses_made_up_values": True}
    ],
    "numbers": [{"value": "5x", "meaning": "throughput", "source": "Section 4.5"}],
    "not_disclosed": ["The data mix"],
}


def rewrite(d):
    out = copy.deepcopy(d)
    out["thesis"] = "Mamba is a sequence model that uses selective state spaces instead of attention."
    out["tabs"][0]["lede"] = "The Overview tab lists the new ideas."
    out["novelties"][0]["why"] = "The parameters depend on the input."
    # A rewrite must not change non-prose fields. The merge keeps the original.
    out["novelties"][0]["status"] = "std"
    out["specs"][0]["value"] = "6x"
    return out


def sse(text, stop_reason="end_turn", model="claude-opus-5-5"):
    events = [
        ("message_start", {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant", "model": model, "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 100, "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None}, "usage": {"output_tokens": 50}}),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in events)


class FakeAPI:
    """A stand-in for the Claude API. It records each request it gets."""

    def __init__(self):
        self.requests = []
        self.extract_stop = "end_turn"
        self.rewrite_fn = rewrite
        self.draft = DRAFT
        self.links = []

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        self.requests.append({"headers": dict(request.headers), "body": body})
        system = body["system"][0]["text"]
        if "<plain_writing_skill>" in system:
            draft = json.loads(body["messages"][0]["content"])
            text, stop = json.dumps(self.rewrite_fn(draft)), "end_turn"
        elif system.startswith("You compare the new ideas"):
            text, stop = json.dumps({"links": self.links}), "end_turn"
        else:
            text, stop = json.dumps(self.draft), self.extract_stop
        return httpx2.Response(200, headers={"content-type": "text/event-stream", "request-id": "req_test"}, text=sse(text, stop))


@pytest.fixture(autouse=True)
def secret_file(tmp_path, monkeypatch):
    """Point the server at a Docker secret file in a temporary folder.

    The file doesn't exist until a test writes it, so no test reads
    /run/secrets on the machine that runs the tests.
    """
    path = tmp_path / "secrets" / "anthropic_api_key"
    path.parent.mkdir()
    monkeypatch.setenv("UNPACKAI_SECRET_FILE", str(path))
    return path


@pytest.fixture
def stored_key(secret_file):
    secret_file.write_text(FAKE_KEY + "\n")
    return FAKE_KEY


@pytest.fixture
def fake_api():
    return FakeAPI()


@pytest.fixture
def unpacker(tmp_path, fake_api):
    db = Database(tmp_path / "test.sqlite3")
    factory = lambda key: anthropic.Anthropic(  # noqa: E731
        api_key=key, max_retries=0, http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(fake_api.handler))
    )
    return Unpacker(db, client_factory=factory)
