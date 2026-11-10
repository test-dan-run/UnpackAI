# ADR 005: Store everything the server generates in SQLite

Status: Accepted

Date: 2026-11-09

## Context

The user asked for a database that stores all the generated items. The server runs as one process on one computer, and it writes a few rows for each paper.

## Options

1. A SQLite file on a volume
2. A PostgreSQL container
3. JSON files in a folder

## Decision

The server stores papers, calls to Claude, and dossier versions in the SQLite file `/data/unpackai.sqlite3` on the `unpackai-data` volume, in WAL mode.

## Consequences

- The project needs no database container, and the volume keeps the data when the containers stop or rebuild.
- Only one server process should write to the file at a time. Running several servers would need a database server.
- The schema version is in `PRAGMA user_version`, and a new column needs a step that changes databases that already exist.
