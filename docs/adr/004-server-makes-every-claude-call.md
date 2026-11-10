# ADR 004: Make every call to Claude in the server, in two calls per paper

Status: Accepted

Date: 2026-11-09

## Context

The app needs Claude to read each paper and write the dossier. The user asked for a backend that reads the API key from a secret store and makes every call to Claude. The generated paragraphs must also follow the plain-writing skill.

## Options

1. The browser calls the Claude API with a key that the user enters
2. A server makes every call, with one call that writes the dossier in plain style
3. A server makes every call, with one call that writes the dossier and a second call that rewrites the prose with the plain-writing skill

## Decision

The server makes every call to Claude in `unpack.py`, and it makes two calls for each paper. The first call fills in the dossier fields by following the unpack skill. The second call rewrites the prose with the plain-writing skill, and the server keeps only the rewritten prose fields.

## Consequences

- The key stays in the server, and the browser never sees it.
- Each paper costs two calls. The second call can't change a status, an evidence label, or a number, because the server takes those from the first call.
- If the rewrite changes the length of a list, the server can't match the rewritten text to the right item, so the unpack fails.
- Both calls use `fallbacks: "default"`, so a declined request can run on Anthropic's recommended fallback model, and the database records which model answered.
