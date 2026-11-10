# ADR 001: Build the prototype as one HTML file

Status: Accepted

Date: 2026-11-09

## Context

The first request was to show how the app could look, with interactive figures that explain a paper. The prototype had to open in a browser right away, and it had to be easy to publish as a single page.

## Options

1. One HTML file with vanilla JavaScript, CSS, and inline SVG
2. A React app with a build step
3. A static site generator with one page for each dossier

## Decision

The prototype is one HTML file, `src/web/index.html`, with vanilla JavaScript and no build step.

## Consequences

- The page opens with no install, and the `app` container serves the file as it is.
- All the dossiers share one script, so every name in a dossier's script block needs the dossier's prefix. A repeated `const` name stops the whole script.
- The file is long, about 1,800 lines with three dossiers, so `docs/repository-map.md` describes the order of its parts.
- The page can't read the server's stored dossiers yet, and connecting it needs new code in the script.
