# UnpackAI server

The server makes every call to Claude for UnpackAI, and it stores everything it generates in a SQLite database. It runs in the `app` container, and the steps to start it are in "Start the app in Docker" in the main `README.md`.

## API key

The server reads the Claude API key from the Docker secret at `/run/secrets/anthropic_api_key`, so the key never appears in the browser, in a request header from the browser, in an environment variable, or in the repository. `scripts/compose-up.sh` reads the key from the keychain on your computer and passes it to Docker Compose, and Compose mounts it in the container as the secret.

The server reads the secret when an unpack needs it, so the server starts even when the key is missing. If the key is missing, the unpack fails with a message that says how to pass the key.

## API

| Method and path | What it does |
| --- | --- |
| `GET /api/health` | Says whether the Docker secret has a key. It never returns the key. |
| `POST /api/unpack` | Starts an unpack. The body is `{"url": "..."}` with an arXiv link or id, a PDF URL, or a blog URL, or `{"text": "..."}` with the full text. |
| `GET /api/papers` | Lists every paper with its status, which is queued, running, done, or failed. |
| `GET /api/papers/{id}` | Returns one paper with its latest dossier. |
| `GET /api/papers/{id}/generations` | Returns every call to Claude for the paper, with the model, the token counts, and the raw output. |

The interactive API documentation is at `/api/docs`. If you send the same source twice, the server returns the stored paper without calling Claude again. It calls Claude again only if the first unpack failed.

The `app` container is published on 127.0.0.1 only, so other computers can't reach the server. Anyone who can reach the server can start an unpack and spend your API credit, so keep the port off public networks.

## How an unpack works

The server makes two calls to Claude for each paper, and it stores both calls in the database.

1. The extract call reads the source and fills in the dossier fields. The system prompt includes the unpack skill from `.claude/skills/unpack/SKILL.md`, so the server follows the same rules as Claude Code. An arXiv paper or PDF goes to Claude as a document URL, and a blog post is read with the web fetch tool.
2. The plain-writing call rewrites every prose field, with the plain-writing skill from `.claude/skills/plain-writing/SKILL.md` as the system prompt. The server keeps only the rewritten prose. Statuses, evidence labels, and numbers come from the first call, so the rewrite can't change them.

After the second call, the server runs the text checks from the unpack skill on every prose field. It stores the problems it finds with the dossier. If either skill file is missing, the unpack stops with an error, as `CLAUDE.md` requires.

Both calls use `claude-opus-5-5` with adaptive thinking. They also use the `fallbacks: "default"` setting, so if Claude declines a request, the API tries Anthropic's recommended fallback model. The `generations` table records which model answered. You can set a different model with the `UNPACKAI_MODEL` variable when you run `scripts/compose-up.sh`.

## Database

The database is a SQLite file at `/data/unpackai.sqlite3` in the `app` container, on the `unpackai-data` volume. The database has three tables:

- `papers` has one row for each source, with its status and any error.
- `generations` has one row for each call to Claude, with the request id, the stop reason, the token counts, the time taken, and the raw output.
- `dossiers` has each finished dossier as JSON, with a version number for each paper and the list of text problems.

## Logging

The logs never contain the API key or request headers, and the server does the following to keep them out:

- The server's request log writes only the method, the path, the status code, and the time taken. The uvicorn access log is turned off, and nothing logs query strings or bodies.
- The Anthropic SDK and the HTTP client libraries are capped at WARNING, and the server removes `ANTHROPIC_LOG` from its environment. At DEBUG level, the SDK logs the full request options and the response headers.
- A filter on every log handler replaces the key, and any `Authorization` or `x-api-key` value, with `[REDACTED]`. The filter is a backup in case a library logs a header anyway.
- The server also removes `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` from its environment, so the Docker secret is the only place the SDK can get a credential.

The test `test_key_comes_from_docker_secret_and_never_reaches_logs_or_responses` checks these rules. It sets the root logger and `ANTHROPIC_LOG` to debug, runs a full unpack, and checks that no log line or API response contains the key or a request header.

## Tests

The tests run in the `test` container, which has no network access. They use a temporary secret file and a fake Claude API, so they don't need a key. Run them from the repository root with the command below, and the `--build` option copies your changes into the image first.

```bash
docker compose --profile test run --rm --build test
```
