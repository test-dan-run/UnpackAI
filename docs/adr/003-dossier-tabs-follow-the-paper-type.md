# ADR 003: Pick the dossier tabs from the paper type

Status: Accepted

Date: 2026-11-09

## Context

The first dossier, for DeepSeek-V3, had Architecture, Data, and Training loop tabs. The user then asked how dataset papers and systems papers would look. A dataset paper puts its new ideas in its processing steps, and a systems paper puts them in how it removes a bottleneck, so the model tabs didn't fit.

## Options

1. Use the same five tabs for every paper
2. Pick the tabs from the paper type, with Overview and Evidence in every dossier
3. Choose new tabs for each paper

## Decision

The paper type sets the tabs between Overview and Evidence. The model, dataset, and systems types have fixed tab lists, and a paper that fits none of them gets three or four tabs by the same rule.

## Consequences

- Readers can compare dossiers of the same type, because the tabs match.
- A new paper type needs a row in the paper type tables of the unpack skill and `docs/architecture.md`.
- The routing in the page reads the tab list of each dossier from `DOCS`, so a dossier can have any number of tabs.
