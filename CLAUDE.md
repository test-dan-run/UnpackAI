# Working rules for UnpackAI

## Plain writing for every paragraph

Every paragraph of prose in the project must go through the `/plain-writing` skill before you commit it or show it. The skill is in `.claude/skills/plain-writing/SKILL.md`. The rule covers the following text:

- The text and explanations in `index.html`, e.g., dossier text, "What to notice" notes, claims, and answers
- Documentation, e.g., `README.md`
- Paragraphs that the app generates when it unpacks a paper

If the skill doesn't load in a session, tell the user and stop. Don't rewrite the text in your own style and say that it went through the skill.

## Unpack requests

Use the `/unpack` skill for every request to unpack a new paper or blog post, e.g., a pasted arXiv link with a request to explain it, or a request to add a dossier. The skill is in `.claude/skills/unpack/SKILL.md`, and it covers reading the source, planning the tabs and figures, building the dossier in `index.html`, and checking the result. If the skill doesn't load in a session, tell the user before you start.

## Calls to Claude

Every call to Claude in the app goes through `server/unpackai_server/unpack.py`. The server reads the API key with `secret_store.py`, from the OS keychain on a computer or from the Docker secret `/run/secrets/anthropic_api_key` in a container. Don't add code that reads the key from an environment variable, any other file, or a request header, and don't log request headers, query strings, or request bodies. Run the server tests after you change the server, because one test checks that the key never reaches the logs.

## Containers

Every part of the project runs in Docker, and `compose.yaml` defines the containers. When you add a dependency or a file that the server or the checks need at run time, add it to `Dockerfile` or `docker/checks.Dockerfile` too, and build and run the container to check it. Don't pass the API key to a container as an environment variable or a build argument, and don't copy it into an image.
