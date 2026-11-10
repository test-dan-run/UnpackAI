# UnpackAI

UnpackAI is a web app that explains new AI research papers and lab blog posts. For each paper, it shows the architecture changes, the data preparation, and the training process, and it marks which ideas are new in the paper and which ideas come from earlier work. Interactive figures show how the new ideas work.

## Purpose

You add a paper by pasting its link, and the app turns the paper into a dossier, which is a page with tabs that explain the paper. Each dossier lists the paper's new ideas with the practice each idea replaces, and it tags each claim by the kind of evidence behind it, e.g., an ablation or a figure the authors report without a separate check. The tabs depend on the paper type, e.g., a dataset paper has tabs for its processing pipeline and its filters.

## Architecture

- A single HTML page with vanilla JavaScript and no build step shows the library and the dossiers.
- A Python server built with FastAPI makes every call to Claude. It serves the page too.
- A SQLite database stores every paper, every call to Claude, and every dossier version.
- Docker Compose runs every part of the project in a container.

The details are in [docs/architecture.md](docs/architecture.md).

## Key components

| Component | Path | What it does |
| --- | --- | --- |
| Page | `src/web/index.html` | Sends links to the server, and shows the library, the stored dossiers, and three sample dossiers |
| Server | `src/server/unpackai_server/` | Unpacks a paper with two calls to Claude and stores the results |
| Skills | `.claude/skills/` | The unpack steps and the plain-writing rules, which Claude Code and the server both use |
| Containers | `compose.yaml`, `docker/` | The `app`, `test`, and `checks` containers |

## Important constraints

- Every paragraph of prose follows the plain-writing skill, including the paragraphs the app generates.
- Every call to Claude goes through `src/server/unpackai_server/unpack.py`.
- The API key reaches the server only as the Docker secret `/run/secrets/anthropic_api_key`. The logs never contain the key or request headers.
- Everything runs in Docker, and the project has no setup outside a container.

## Start the app

You need Docker with Compose and a keychain on your computer, e.g., macOS Keychain or GNOME Keyring on Linux. Run the commands from the repository root.

First, store your Claude API key in the keychain. The keychain tool asks for the key and hides what you type, and you only need to store the key once.

```bash
scripts/store-key.sh
```

Second, build and start the app container. The script reads the key from the keychain and passes it to Docker Compose only for the start command.

```bash
scripts/compose-up.sh
```

Third, open http://127.0.0.1:8000 in a browser. To unpack a paper, paste an arXiv link, a PDF URL, or a blog URL in the bar at the top, and click Unpack. The bar shows each step while the server works, and the library shows the paper when its dossier is ready.

To run the server tests and the page checks, use the commands below. The `--build` option copies your latest changes into the images first.

```bash
docker compose --profile test run --rm --build test
```

```bash
docker compose --profile checks run --rm --build checks
```

## Documentation

| Document | What it answers |
| --- | --- |
| [AGENTS.md](AGENTS.md) | What an AI agent reads first, which rules it follows, and what a finished change includes |
| [docs/architecture.md](docs/architecture.md) | How the page, the server, the database, and the containers fit together |
| [docs/repository-map.md](docs/repository-map.md) | Where each file is, and where new work goes |
| [docs/coding-standards.md](docs/coding-standards.md) | How to write the prose, the page, the server code, and the tests |
| [docs/adr/](docs/adr/) | Why the project made each design decision |
| [docs/examples/](docs/examples/) | Examples from the project to copy for new work |

The plain-writing skill in `.claude/skills/plain-writing/` is copied from [docwriter-org/plain-writing-skill](https://github.com/docwriter-org/plain-writing-skill) at commit `f0d3630`. It is under the MIT license, and the license file is in the same folder.
