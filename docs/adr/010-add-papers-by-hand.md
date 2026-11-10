# ADR 010: Add papers by hand

Status: Accepted

Date: 2026-11-10

## Context

The first design of the page had a step that collected new papers from arXiv categories and from the RSS feeds of lab blogs, and the library listed the sources it followed. Each unpack makes two calls to Claude with a large model, so automatic collection would spend API credit on papers that nobody reads. The user decided to add papers by hand.

## Options

1. Collect new papers from arXiv cs.CL and cs.LG and from lab blog feeds on a schedule
2. Add each paper by hand, with a link in the command bar or a request to `POST /api/unpack`

## Decision

UnpackAI uses option 2. The library lists the papers that someone added, and the three sample dossiers.

## Consequences

- The server has no schedule and no list of feeds, and every unpack starts from a request.
- The library says how to add a paper, and it doesn't list followed sources.
- Automatic collection needs a new ADR. It would also need a limit on the number of unpacks in a day, and a rule for which papers to unpack.
