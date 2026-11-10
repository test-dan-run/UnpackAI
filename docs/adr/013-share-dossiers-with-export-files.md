# ADR 013: Share dossiers with export files

Status: Accepted

Date: 2026-11-10

## Context

Each person runs UnpackAI on their own computer with their own database and API key, and the server is published on 127.0.0.1 only (ADR 006 and ADR 008). People want to share the dossiers they unpacked, so another person can read a dossier without unpacking the paper again with their own API credit. The paper ids differ between libraries, and a dossier links its ideas to earlier dossiers by paper id (ADR 012). A dossier from another person also can't be trusted more than text from a paper, because the person can change the file.

## Options

1. Export the whole SQLite database, and let another person replace their database with it
2. Export the latest dossier of each finished paper to a JSON file, and import the file into another library
3. Run a shared server that many people can reach

## Decision

UnpackAI uses option 2. `GET /api/export` returns a file with every finished dossier, and `GET /api/papers/{id}/export` returns a file with one dossier. `POST /api/import` reads a file and adds its papers to the library. The page has an Export the dossier button on each stored dossier, and the library has Export the library and Import a file buttons. `share.py` holds the file format and the checks.

The file names each paper by its source key, e.g., `arxiv:2312.00752`, and a link to an earlier dossier names the earlier paper by its source key too. When a library imports the file, the server sets each link to the id of the paper with that source in the library. A link to a paper that isn't in the library keeps the title and the idea text with no id, so the page shows the title without a link.

The server checks every dossier in the file against the dossier schema, and it accepts only http and https URLs. If any paper in the file has a problem, the server stores none of the papers. It skips a paper whose source is already in the library, unless the unpack of that paper failed, and then the imported dossier replaces the failed unpack. The server runs the text check on each imported dossier and marks the dossier with the origin `import`, so the page can say that the dossier came from an export file.

## Consequences

- People can share dossiers without sharing an API key, a database, or a server that other computers can reach.
- The file holds no calls to Claude, raw output, errors, or text problems, so it doesn't show how much the unpack cost or what Claude returned.
- The imported dossier went through the plain-writing call in the library that made it, but the person who sends the file can change the text. The text check runs again on import, and the page escapes every value as it does for any dossier from the server.
- A link to a paper that isn't in the library stays without an id, even if the library imports that paper later. Importing the earlier paper first, or both papers in one file, keeps the link.
- The compare call sees the ideas of imported dossiers, so a new unpack can link to them.
- The file holds only the latest version of each dossier.
