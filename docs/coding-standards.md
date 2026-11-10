# Coding standards

The standards below cover the prose, the page, the server, the tests, and the containers. The examples in [docs/examples/](examples/) show each standard in code from the project.

## Prose

Every paragraph follows the plain-writing skill in `.claude/skills/plain-writing/SKILL.md`. The rule covers the text in `src/web/index.html`, the documentation, the comments that explain a design, and the paragraphs the server generates.

- Use simple words and complete sentences, with at most two clauses in a sentence.
- Don't use dashes, middle dots, curly quotes, or colons that join two clauses.
- Don't use a demonstrative pronoun as the subject of a sentence, and don't use analogies or catchy labels.
- Use sentence case in headings, and keep lists to four items or fewer, with nested items for more.

The text check in `src/server/unpackai_server/text_check.py` finds the problems that a script can find. Read the text against the skill as well, because most rules need a person or a model to judge them.

## Page

- Keep the page in one file with no build step. The page loads only the Google Fonts stylesheet from outside, and every script and style is inline.
- Give each dossier a short id, e.g., `fineweb`, and a two-letter prefix, e.g., `FW` and `fw`. Put the prefix on every element id and every top-level name in the dossier's script block, because all the dossiers share one script. Don't use an id of the form `p` and a number, because the stored dossiers use those ids.
- Escape every value from the server with `esc()` before you add it to the page, e.g., a title, an error, or a field of a stored dossier.
- Call the server only when `API_ON` is true, so the page still works when you open it as a file.
- Use the color tokens, e.g., `--hl`, `--inh`, `--std`, `--ink`, and `--paper`, and don't write fixed colors. The tokens have a second set for dark mode.
- Reuse the existing CSS classes. Put a new rule before `@media (max-width:1100px)`, and add a rule for 620px and less when the layout needs one.
- Make the page work at 400px width with no sideways scroll.

### Interactive figures

- Use the paper's numbers. When a figure needs values that the paper doesn't give, add a `<p class="proto-note">` that says which values are made up.
- Compute the output from the inputs, so the output stays correct when the reader moves a control.
- Add a `<p class="notice"><b>What to notice:</b> ...</p>` note that says what to look for and how it relates to the paper's result.
- Give each SVG and each group of buttons an `aria-label`, and give each slider a `<label>`.

## Server

- Make every call to Claude in `unpack.py`, through `Unpacker._call()`. The method stores each call in the `generations` table, including failed calls.
- Use the model `claude-opus-5-5` unless `UNPACKAI_MODEL` names another one. Use streaming with adaptive thinking, structured output with the dossier schema, and `fallbacks: "default"`.
- Every prose field goes through the plain-writing call. A new call that returns prose must run before the plain-writing call, and its fields must be in `PROSE_FIELDS`. A call that returns only links, statuses, or numbers can run at any step.
- Check `stop_reason` before you read the content, and treat `refusal` and `max_tokens` as failures.
- Read the API key only with `secret_store.read_api_key()`. Don't read it from an environment variable, any other file, or a request header.
- Log only the method, the path, the status code, and the time taken for a request. Don't log headers, query strings, or bodies, and pass every error message through `describe_error()` before you store or log it.
- Keep error messages short and specific, and say what the user can do, e.g., which script to run.
- Treat an export file like text from a paper, because another person can change it. Check it with `share.check_export()` before you store any part of it, and don't trust a paper id from the file.

## Tests

- Put the server tests in `tests/server/`. The tests use the fake Claude API and the temporary secret file from `conftest.py`, so they need no key and no network.
- Add a test for each new endpoint or unpack step, and assert on what the user sees, e.g., the stored status and error.
- Run the tests in the `test` container after every change to the server.
- Keep the browser check in `tests/web/check_dossiers.js` generic. It reads the dossiers and tabs from the page, so a new dossier needs no change to the check.
- When the page uses a new endpoint or a new field from the server, add it to the fake server in `tests/web/fake_server.js`.

## Containers

- Run everything in a container, and don't add a way to run the server, the tests, or the checks outside one.
- When the server or the checks need a new file or package at run time, add it to `docker/app.Dockerfile` or `docker/checks.Dockerfile`, and build and run the container.
- Don't pass the API key as an environment variable of a container or as a build argument, and don't copy it into an image.
- Pin base image versions with a tag, and keep the `playwright` package version equal to the Playwright image version.

## Commits

- Write the commit message with the plain-writing skill. The first line says what changed, and the body says why.
- Keep one change in each commit, e.g., a new dossier, or a server change with its tests.
