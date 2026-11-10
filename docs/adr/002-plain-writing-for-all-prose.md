# ADR 002: Write every paragraph with the plain-writing skill

Status: Accepted

Date: 2026-11-09

## Context

The app explains research papers to readers who may not know the field, so the text has to be easy to understand in one pass. The user asked for every generated paragraph to go through the plain-writing skill.

## Options

1. Write a style guide for the project
2. Copy the plain-writing skill into the repository and require it for all prose
3. Leave the style to each writer

## Decision

The project copies the skill from [docwriter-org/plain-writing-skill](https://github.com/docwriter-org/plain-writing-skill) at commit `f0d3630` into `.claude/skills/plain-writing/`, under its MIT license. Every paragraph in the page, the documentation, and the server's output follows the skill.

## Consequences

- If the skill doesn't load in a Claude Code session, the session stops and tells the user, so no text claims to follow a skill it didn't use.
- The server uses the skill as the system prompt of its second call, and it stops an unpack when the skill file is missing.
- The text check in `text_check.py` finds the problems that a script can find, e.g., dashes and curly quotes, and the `checks` container runs it on the page and the documentation.
- The copied skill's own examples break the rules on purpose, so the text check skips the skill's folder.
