# Repository map

The repository follows the layout in [How I Structure Repositories So AI Can Actually Understand Them](https://suyogjoshi.com/writing/how-i-structure-repositories-so-ai-can-understand-them/), and ADR 009 records the choice. The application code is in `src/`, the tests are in `tests/`, and the documentation is in `docs/`.

```
UnpackAI/
|-- README.md                 What the app is for, and how to start it
|-- AGENTS.md                 Rules for AI agents that change the repository
|-- CLAUDE.md                 Loads AGENTS.md for Claude Code, plus the skill rules
|-- compose.yaml              The app, test, and checks containers
|
|-- docs/
|   |-- architecture.md       How the page, the server, and the containers fit together
|   |-- repository-map.md     This file
|   |-- coding-standards.md   How to write the prose and the code
|   |-- adr/                  One file for each design decision
|   `-- examples/             Examples from the project to copy for new work
|
|-- src/
|   |-- web/
|   |   `-- index.html        The prototype page, with every dossier
|   `-- server/
|       |-- requirements.txt  The server's Python packages
|       `-- unpackai_server/  The server package
|
|-- tests/
|   |-- server/               The server tests, run in the test container
|   `-- web/
|       |-- check_dossiers.js The browser check, run in the checks container
|       `-- fake_server.js    The fake API that the browser check uses
|
|-- scripts/
|   |-- store-key.sh          Stores the API key in the host keychain
|   `-- compose-up.sh         Starts the app container with the key as a Docker secret
|
|-- docker/
|   |-- app.Dockerfile        The image for the app and test containers
|   |-- checks.Dockerfile     The image for the checks container
|   `-- run-checks.sh         The command that the checks container runs
|
`-- .claude/skills/
    |-- unpack/SKILL.md       The steps for unpacking a paper into a dossier
    `-- plain-writing/        The plain-writing rules, copied with their license
```

## The page

`src/web/index.html` holds the whole page, in this order:

- The `<style>` block, which starts with the color tokens on `:root` and the dark mode tokens. The CSS for the dataset and systems dossiers comes before `@media (max-width:1100px)`.
- The header with the command bar and the unpack progress, and the library in `<aside class="library">`.
- `<main class="dossier" id="dossier">`, with one `<div class="doc" data-doc="<id>">` for each dossier. Each one has a paper head, a `nav.tabs`, and one `section.panel[data-panel]` for each tab.
- The `<script>` block, in this order:
  - The shared helpers, e.g., `esc()` and `toast()`, and the library in `LIB` and `renderLib()`
  - The server connection, with names that start with `api` or `API_`, and the stored dossier template, with names that start with `gen` or `GEN_`
  - The routing in `DOCS`, `parseHash()`, and `showTab()`
  - One block for each sample dossier. Every name in a block starts with the dossier's prefix, e.g., `FW_` and `fw` for FineWeb, and the blocks use the shared helpers `noveltyRows()`, `claimsHTML()`, `detailHTML()`, and `makeSeg()`.

## The server package

| File | What it does |
| --- | --- |
| `__main__.py` | Starts uvicorn with the safe log setup |
| `app.py` | Defines the HTTP endpoints, serves the page, and writes the request log |
| `unpack.py` | Parses sources and makes every call to Claude, with the extract, compare, and plain-writing prompts |
| `dossier_schema.py` | Defines the JSON schemas of a dossier and of the compare links, adds the links to a draft, merges the rewritten prose into the draft, and checks that a dossier matches the schema |
| `db.py` | Creates the SQLite tables, reads and writes papers, generations, and dossiers, and finds the links between dossiers |
| `share.py` | Builds export files, and checks and imports export files from other libraries |
| `secret_store.py` | Reads the API key from the Docker secret |
| `safe_logging.py` | Caps the library loggers, and redacts the key and auth headers in every log handler |
| `text_check.py` | Checks text for the plain-writing rules that a script can check. The server imports it, and the checks container runs it as a script. |

## The tests

| File | What it has |
| --- | --- |
| `tests/server/conftest.py` | The fake Claude API, the temporary Docker secret file, and the example dossier drafts |
| `tests/server/test_server.py` | The tests for the endpoints, the unpack steps, the secret, and the logs |
| `tests/server/test_share.py` | The tests for export files, imports, and bad files |
| `tests/server/requirements.txt` | The server packages plus pytest |
| `tests/web/check_dossiers.js` | Opens every tab of every dossier, with the page open as a file and from the fake server, and reports problems |
| `tests/web/fake_server.js` | Answers the page's API requests with a stored dossier, an imported dossier, a running unpack, and a failed unpack |

## Decisions

| ADR | Decision |
| --- | --- |
| [001](adr/001-single-file-prototype-page.md) | The prototype is one HTML file with no build step |
| [002](adr/002-plain-writing-for-all-prose.md) | Every paragraph follows the plain-writing skill |
| [003](adr/003-dossier-tabs-follow-the-paper-type.md) | The paper type sets the tabs of a dossier |
| [004](adr/004-server-makes-every-claude-call.md) | The server makes every call to Claude, with a plain-writing call after the extract call |
| [005](adr/005-sqlite-for-generated-items.md) | SQLite stores everything the server generates |
| [006](adr/006-api-key-from-a-docker-secret.md) | The API key reaches the server as a Docker secret from the host keychain |
| [007](adr/007-no-secrets-or-headers-in-logs.md) | The logs never contain the key or request headers |
| [008](adr/008-docker-only.md) | Every part of the project runs in Docker |
| [009](adr/009-repository-layout-for-people-and-ai-agents.md) | The repository follows a layout with documentation for people and AI agents |
| [010](adr/010-add-papers-by-hand.md) | Papers are added by hand, and UnpackAI doesn't collect them on its own |
| [011](adr/011-page-builds-stored-dossiers-from-json.md) | The page builds each stored dossier from the JSON with one template |
| [012](adr/012-compare-with-earlier-dossiers-in-a-separate-call.md) | A separate call links the new ideas to the ideas in earlier dossiers, and it returns no prose |
| [013](adr/013-share-dossiers-with-export-files.md) | People share dossiers with export files, which the server checks before it imports them |

## Where new work goes

| Change | Where it goes |
| --- | --- |
| A dossier for a new paper | `src/web/index.html`, by following `.claude/skills/unpack/SKILL.md` |
| A new paper type | The paper type tables in `.claude/skills/unpack/SKILL.md` and `docs/architecture.md` |
| A new kind of interactive figure | `src/web/index.html`, and a row in the figure table of the unpack skill |
| A new endpoint | `src/server/unpackai_server/app.py`, with a test in `tests/server/test_server.py`. If the page calls it, add it to `tests/web/fake_server.js` too. |
| A change to how the page shows stored dossiers | `genBuild()` in `src/web/index.html`, and the fake dossier in `tests/web/fake_server.js` |
| A change to how the server calls Claude | `src/server/unpackai_server/unpack.py` |
| A new dossier field | `src/server/unpackai_server/dossier_schema.py`, and `PROSE_FIELDS` if the field is prose. If the export file needs a change for the field, raise `VERSION` in `share.py`. |
| A new table or column | `src/server/unpackai_server/db.py`. Raise `SCHEMA_VERSION`, and add a step that changes databases that already exist, because `CREATE TABLE IF NOT EXISTS` doesn't add columns. |
| A new Python package for the server | `src/server/requirements.txt` |
| A new file that a container needs | The `COPY` lines in `docker/app.Dockerfile` or `docker/checks.Dockerfile` |
| A new design decision | A new file in `docs/adr/`, and a row in the table above |
