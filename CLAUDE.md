# Working rules for UnpackAI

@AGENTS.md

The rules below are only for Claude Code, and they add to the rules in `AGENTS.md`.

## Plain writing for every paragraph

Load the `/plain-writing` skill before you write or change any prose, and use it for every paragraph before you commit it or show it. The rule covers the following text:

- The text and explanations in `src/web/index.html`, e.g., dossier text, "What to notice" notes, claims, and answers
- Documentation, e.g., `README.md`, `AGENTS.md`, and the files in `docs/`
- Paragraphs that the app generates when it unpacks a paper

If the skill doesn't load in a session, tell the user and stop. Don't rewrite the text in your own style and say that it went through the skill.

## Unpack requests

Use the `/unpack` skill for every request to unpack a new paper or blog post, e.g., a pasted arXiv link with a request to explain it, or a request to add a dossier. The skill covers reading the source, planning the tabs and figures, building the dossier in `src/web/index.html`, and checking the result. If the skill doesn't load in a session, tell the user before you start.
