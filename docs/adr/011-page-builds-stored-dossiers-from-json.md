# ADR 011: Build stored dossiers in the page from the JSON

Status: Accepted

Date: 2026-11-10

## Context

The server stores each dossier as JSON, and before the change the page showed only the sample dossiers, which Claude Code built by hand. The page has to show stored dossiers and the results of the text check, with no build step (ADR 001). The text in a dossier comes from a paper or a web page, so it can contain HTML.

## Options

1. The server renders the HTML for each dossier
2. The page builds each stored dossier from the JSON with one template
3. Claude Code builds each stored dossier by hand with the unpack skill, as it did for the sample dossiers

## Decision

UnpackAI uses option 2. When you open a stored dossier, the page loads it from `GET /api/papers/{id}`, and `genBuild()` turns the JSON into the same paper head, tabs, and panels that the sample dossiers use. The page escapes every value with `esc()`. It also adds a Text check tab, which lists the problems that the server's text check found and the calls to Claude.

## Consequences

- Every stored dossier has the same layout. A suggested figure shows only its title and its "What to notice" note, because the template has no interactive figures.
- The unpack skill still builds a dossier by hand, with interactive figures, when you ask Claude Code for one.
- The server returns only JSON, and the page builds every view.
- The browser check tests the template with a fake server, and the fake dossier has HTML in its title to test the escaping.
