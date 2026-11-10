# AGENTS.md

The rules below are for AI agents that change the UnpackAI repository. They apply to every agent, and `CLAUDE.md` adds the rules that are only for Claude Code.

## Before making changes

1. Read `README.md` and `docs/architecture.md`.
2. Find the files for the change in `docs/repository-map.md`, which also says where new work goes.
3. Read the ADRs in `docs/adr/` that cover the part you change.
4. Follow `docs/coding-standards.md`, and copy the patterns in `docs/examples/`.

For a request to unpack a new paper or blog post, follow `.claude/skills/unpack/SKILL.md`. For any prose, follow `.claude/skills/plain-writing/SKILL.md`.

## Architecture constraints

- The prototype is the single file `src/web/index.html`, with vanilla JavaScript and no build step.
- Every call to Claude goes through `src/server/unpackai_server/unpack.py`.
- The server reads the API key only from the Docker secret `/run/secrets/anthropic_api_key`, with `secret_store.py`.
- Every part of the project runs in a container that `compose.yaml` defines.

## Development rules

- Every paragraph of prose follows the plain-writing skill, including the page text, the documentation, comments that explain a design, and the paragraphs the server generates.
- Every number in a dossier comes from the paper, and every made-up value in a figure has a `proto-note`.
- Add a test in `tests/server/` for each change to the server, and run the tests with `docker compose --profile test run --rm --build test`.
- Run the checks with `docker compose --profile checks run --rm --build checks` after you change the page or the documentation.
- When the server or the checks need a new file or package at run time, add it to `docker/app.Dockerfile` or `docker/checks.Dockerfile`, and build and run the container.
- Record a new design decision as an ADR in `docs/adr/`, and update `docs/architecture.md` and `docs/repository-map.md` when the structure changes.

## Forbidden actions

- Don't read the API key from an environment variable, a file other than the Docker secret, or a request header.
- Don't pass the API key to a container as an environment variable or a build argument, and don't copy it into an image.
- Don't log request headers, query strings, or request bodies.
- Don't add a way to run the server, the tests, or the checks outside a container.
- Don't add a build step, a framework, or an outside script to the page.
- Don't guess a value that the paper doesn't disclose. Say in the dossier that the paper doesn't give it.

## Pull request checklist

- The `test` and `checks` containers pass.
- The prose follows the plain-writing skill, and the text check reports no problems.
- The documentation in `README.md` and `docs/` matches the change.
- The change respects the architecture constraints and the ADRs, or a new ADR replaces the old decision.
