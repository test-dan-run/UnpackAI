# ADR 012: Compare each paper with earlier dossiers in a separate call

Status: Accepted

Date: 2026-11-10

## Context

A dossier marks each idea as new, inherited, or standard. Before the change, the extract call marked an idea as inherited only when the paper cited earlier work for it, so the dossier couldn't show that a paper in the library already had the same idea. The reader also couldn't move from an idea to the dossier where it first appeared. Every prose field has to go through the plain-writing call (ADR 002 and ADR 004).

## Options

1. Add the ideas of the earlier dossiers to the extract call
2. Make a third call after the extract call, which returns only links between the new ideas and the earlier ideas
3. Compare the ideas in the server with text matching, with no call to Claude

## Decision

UnpackAI uses option 2. After the extract call, the compare call gets the new ideas and the ideas of the latest dossier of every finished paper, and it returns a list of links. Each link names a new idea, an earlier paper, an earlier idea, and a relation, which is `same_idea` or `builds_on`. The server checks each link and adds it to the new idea as an `earlier` field. A new idea that is the same idea as an earlier one is marked as inherited.

## Consequences

- The links hold no new prose, so the plain-writing call doesn't need to rewrite them. The page builds the link text from the earlier idea's text, which already went through the skill.
- The extract call stays the same, so its prompt and its cached system prompt don't depend on the library.
- The server skips the compare call when the library has no other finished dossier, so the first paper still costs two calls.
- The API lists, for each paper, the later papers whose ideas link to it, so the page can show the links in both directions.
- The sample dossiers in the page aren't in the database, so the compare call doesn't see their ideas.
- The compare call sends the ideas of every earlier dossier. A large library will need a search step that picks the closest dossiers first.
