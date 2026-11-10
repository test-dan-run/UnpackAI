# Good server test

The server tests in `tests/server/test_server.py` run in the `test` container, with a fake Claude API and a temporary Docker secret file from `conftest.py`. They need no key and no network.

## Fixture

The `client` fixture starts the app with a stored key and the fake API. A test that needs a missing key leaves out `stored_key`, and the secret file then doesn't exist.

```python
@pytest.fixture
def client(unpacker, stored_key):
    with TestClient(create_app(unpacker=unpacker)) as c:
        yield c
```

## Test

The test below covers one behavior from the user's side. It makes the fake API decline the first call, and it checks the stored status, the error, and the stored call. It then checks that the same request works when the API answers.

```python
def test_refusal_is_stored_and_the_failed_paper_can_be_retried(client, fake_api):
    fake_api.extract_stop = "refusal"
    pid = client.post("/api/unpack", json={"url": "2312.00752"}).json()["paper_id"]
    paper = client.get(f"/api/papers/{pid}").json()
    assert paper["status"] == "failed" and "declined" in paper["error"]
    gens = client.get(f"/api/papers/{pid}/generations").json()
    assert gens[0]["stop_reason"] == "refusal" and gens[0]["error"]

    fake_api.extract_stop = "end_turn"
    assert client.post("/api/unpack", json={"url": "2312.00752"}).json()["queued"] is True
    assert client.get(f"/api/papers/{pid}").json()["status"] == "done"
```

## Checklist

- The test goes through the HTTP endpoints, the way the page or a user would.
- The test sets the fake API's answer, e.g., `extract_stop` or `rewrite_fn`, instead of patching the server code.
- The test checks what is stored in the database, because the database keeps every generated item.
- A test that touches logging or the secret also checks that the key isn't in the logs or the responses.
