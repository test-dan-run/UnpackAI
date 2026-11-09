# Working rules for UnpackAI

## Plain writing for every paragraph

Every paragraph of prose in the project must go through the `/plain-writing` skill before you commit it or show it. The skill is in `.claude/skills/plain-writing/SKILL.md`. The rule covers the following text:

- The text and explanations in `index.html`, e.g., dossier text, "What to notice" notes, claims, and answers
- Documentation, e.g., `README.md`
- Paragraphs that the app generates when it unpacks a paper

If the skill doesn't load in a session, tell the user and stop. Don't rewrite the text in your own style and say that it went through the skill.
