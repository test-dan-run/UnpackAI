# ADR 009: Lay out the repository for people and AI agents

Status: Accepted

Date: 2026-11-10

## Context

AI agents make most changes in the repository, so the purpose, the structure, the decisions, and the rules have to be written down where an agent can find them. The user asked for the layout in [How I Structure Repositories So AI Can Actually Understand Them](https://suyogjoshi.com/writing/how-i-structure-repositories-so-ai-can-understand-them/). Before the change, the page and the Dockerfile were at the root, the server and its tests were in `server/`, and the check scripts were inside the unpack skill.

## Options

1. Keep the layout, and add documentation to the README
2. Follow the post's layout, with `AGENTS.md`, `docs/`, `src/`, `tests/`, and `scripts/`

## Decision

The repository follows the post's layout:

- `README.md` says what the app is for, and `AGENTS.md` says how an agent works in the repository.
- `docs/` has the architecture, the repository map, the coding standards, the ADRs, and the examples.
- `src/web/` has the page, `src/server/` has the server, and `tests/` has the server tests and the browser check.
- `scripts/` has the host scripts, and `docker/` has the Dockerfiles.

## Consequences

- `CLAUDE.md` imports `AGENTS.md`, so Claude Code and other agents read the same rules. `CLAUDE.md` adds only the rules about Claude Code skills.
- The skills stay in `.claude/skills/`, because Claude Code loads skills only from there.
- The text check moved into the server package as `text_check.py`, because the server imports it and the checks container runs it as a script.
- The documentation has to change with the code. A change to the layout, a rule, or a decision updates the matching file in `docs/`.
