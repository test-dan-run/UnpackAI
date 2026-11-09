# UnpackAI server

The server makes every call to Claude for UnpackAI, and it stores everything it generates in a SQLite database. It reads the Claude API key from a secret store, so the key never appears in the browser, in a request header from the browser, in an environment variable, or in the repository.

## Secret stores

The `UNPACKAI_SECRET_SOURCE` variable picks the secret store, and the variable never holds the key itself.

| `UNPACKAI_SECRET_SOURCE` | Where the key comes from | When to use it |
| --- | --- | --- |
| `keychain` (the default) | The OS keychain, under service `unpackai` and account `anthropic_api_key` | The server runs directly on your computer |
| `docker-secret` | The Docker secret at `/run/secrets/anthropic_api_key` | The server runs in a container. The image sets `docker-secret` as the source. |

To run the server in Docker, follow the steps in "Run everything in Docker" in the main `README.md`. The steps below run the server directly on your computer.

## Set up the server without Docker

First, install the dependencies in a virtual environment.

```bash
cd server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Second, store your API key in the OS keychain. The command asks for the key without showing it, so the key isn't saved in your shell history.

```bash
.venv/bin/python -m unpackai_server.set_key
```

The key is stored under the service name `unpackai` and the account name `anthropic_api_key`. On macOS it's in Keychain Access, and on Windows it's in Credential Manager. On Linux it's in the Secret Service, e.g., GNOME Keyring, which has to be installed and unlocked.

Third, start the server and open http://127.0.0.1:8000 in a browser.

```bash
.venv/bin/python -m unpackai_server
```

The server listens on 127.0.0.1 by default, so only your own computer can reach it. Anyone who can reach the server can start an unpack and spend your API credit, so don't use `--host 0.0.0.0` unless the network is private.

## API

| Method and path | What it does |
| --- | --- |
| `GET /api/health` | Names the secret store and says whether it has a key. It never returns the key. |
| `POST /api/unpack` | Starts an unpack. The body is `{"url": "..."}` with an arXiv link or id, a PDF URL, or a blog URL, or `{"text": "..."}` with the full text. |
| `GET /api/papers` | Lists every paper with its status, which is queued, running, done, or failed. |
| `GET /api/papers/{id}` | Returns one paper with its latest dossier. |
| `GET /api/papers/{id}/generations` | Returns every call to Claude for the paper, with the model, the token counts, and the raw output. |

The interactive API documentation is at `/api/docs`. If you send the same source twice, the server returns the stored paper without calling Claude again. It calls Claude again only if the first unpack failed.

## How an unpack works

The server makes two calls to Claude for each paper, and it stores both calls in the database.

1. The extract call reads the source and fills in the dossier fields. The system prompt includes the unpack skill from `.claude/skills/unpack/SKILL.md`, so the server follows the same rules as Claude Code. An arXiv paper or PDF goes to Claude as a document URL, and a blog post is read with the web fetch tool.
2. The plain-writing call rewrites every prose field, with the plain-writing skill from `.claude/skills/plain-writing/SKILL.md` as the system prompt. The server keeps only the rewritten prose. Statuses, evidence labels, and numbers come from the first call, so the rewrite can't change them.

After the second call, the server runs the text checks from the unpack skill on every prose field. It stores the problems it finds with the dossier. If either skill file is missing, the unpack stops with an error, as `CLAUDE.md` requires.

Both calls use `claude-opus-5-5` with adaptive thinking. They also use the `fallbacks: "default"` setting, so if Claude declines a request, the API tries Anthropic's recommended fallback model. The `generations` table records which model answered. You can set a different model with the `UNPACKAI_MODEL` environment variable.

## Database

The database is a SQLite file at `server/data/unpackai.sqlite3`, and git ignores the folder. You can set a different path with the `UNPACKAI_DB` environment variable. The database has three tables:

- `papers` has one row for each source, with its status and any error.
- `generations` has one row for each call to Claude, with the request id, the stop reason, the token counts, the time taken, and the raw output.
- `dossiers` has each finished dossier as JSON, with a version number for each paper and the list of text problems.

## Logging

The logs never contain the API key or request headers, and the server does the following to keep them out:

- The server's request log writes only the method, the path, the status code, and the time taken. The uvicorn access log is turned off, and nothing logs query strings or bodies.
- The Anthropic SDK and the HTTP client libraries are capped at WARNING, and the server removes `ANTHROPIC_LOG` from its environment. At DEBUG level, the SDK logs the full request options and the response headers.
- A filter on every log handler replaces the key, and any `Authorization` or `x-api-key` value, with `[REDACTED]`. The filter is a backup in case a library logs a header anyway.
- The server also removes `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` from its environment, so the secret store is the only place the SDK can get a credential.

The test `test_key_comes_from_keychain_and_never_reaches_logs_or_responses` checks these rules. It sets the root logger and `ANTHROPIC_LOG` to debug, runs a full unpack, and checks that no log line or API response contains the key or a request header.

## Tests

The tests use an in-memory keychain, a temporary Docker secret file, and a fake Claude API, so they don't need a key or a network connection. To run them in a container, run `docker compose --profile test run --rm test` from the repository root. To run them on your computer, use the commands below.

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```
