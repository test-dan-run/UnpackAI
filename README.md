# UnpackAI

UnpackAI is a web app that explains new AI research papers and lab blog posts. For each paper, it shows the architecture changes, the data preparation, and the training process, and it marks which ideas are new in the paper and which ideas come from earlier work. Interactive figures show how the new ideas work.

The project has a clickable prototype page, a small Python server that makes every call to Claude and stores the results, and Docker containers that run every part of the project.

## Start the app in Docker

You need Docker with Compose and a keychain on your computer, e.g., macOS Keychain or GNOME Keyring on Linux. Run the commands from the repository root.

First, store your Claude API key in the keychain. The keychain tool asks for the key and hides what you type, and you only need to store the key once.

```bash
scripts/store-key.sh
```

Second, build and start the app container. The script reads the key from the keychain and passes it to Docker Compose only for the start command.

```bash
scripts/compose-up.sh
```

Third, open http://127.0.0.1:8000 in a browser.

## Repository layout

| Path | What it has |
| --- | --- |
| `index.html` | The prototype page, with three complete dossiers |
| `server/` | The Python server, its tests, and its own README |
| `.claude/skills/` | The unpack skill and the plain-writing skill |
| `Dockerfile`, `docker/`, `compose.yaml` | The container definitions |
| `scripts/` | The scripts that store the API key and start the app container |
| `CLAUDE.md` | The working rules for Claude Code in the project |

## Prototype page

The file `index.html` is a clickable prototype, and the `app` container serves it at http://127.0.0.1:8000. It has complete dossiers for three papers, one of each paper type, and the other library entries show how the list of papers would look.

The page has three parts:

- The command bar at the top takes an arXiv link, a blog URL, or a PDF. The Unpack button shows a mock of the processing steps, because the page doesn't call the server yet.
- The library on the left lists the papers and posts from the sources you follow. You can filter the library by area, e.g., architecture or data, and each entry shows whether it has been unpacked.
- The dossier on the right explains one paper in tabs. Every dossier starts with an Overview tab, which has a table of the paper's new ideas with what each idea replaces and why it works. Every dossier ends with an Evidence tab, which tags each claim by the kind of evidence behind it, e.g., an ablation or a figure the authors report without a separate check.

The colors have a fixed meaning on every page. Yellow marks an idea that is new in the paper, blue marks an idea from earlier work, and grey marks standard practice.

## Paper types

UnpackAI picks the tabs between Overview and Evidence from the type of paper, because each type puts its new ideas in a different place.

| Paper type | Example in the prototype | Tabs between Overview and Evidence |
| --- | --- | --- |
| Model paper | DeepSeek-V3 Technical Report (arXiv 2412.19437) | Architecture, Data, Training loop |
| Dataset paper | The FineWeb Datasets (arXiv 2406.17557) | Pipeline, Filters, Deduplication, FineWeb-Edu |
| Systems paper | FlashAttention (arXiv 2205.14135) | Bottleneck, Algorithm, Performance |

The model dossier has a simulation of how the router balances work across experts, a KV cache calculator, a learning rate timeline, and an FP8 rounding heatmap. Its Data tab shows which parts of the data preparation the report discloses, with examples of fill-in-the-middle and document packing.

The dataset dossier has a pipeline diagram, a filter tester that computes page statistics from example pages, and a simulation of the two ways to deduplicate across crawl snapshots. Its Evidence tab also lists what the authors released, e.g., the data, the code, and the ablation models.

The systems dossier has a roofline estimate that shows why standard attention is limited by memory traffic, and an animation of the loop over tiles. It also has a worked example of the online softmax and a calculator that compares HBM traffic for standard attention and FlashAttention. Its Performance tab names the baseline for each speedup, because the paper uses different baselines for different results.

## Server

The server in `server/` makes every call to Claude, and it stores everything it generates in a SQLite database. You send it a source, e.g., an arXiv link, a PDF URL, a blog URL, or pasted text, and it makes two calls to Claude for the source. First, it fills in the dossier fields by following the unpack skill. Second, it rewrites every paragraph with the plain-writing skill. The server keeps the statuses, evidence labels, and numbers from the first call, so the rewrite can't change them.

The database stores each paper, every call to Claude with its token counts and raw output, and each version of the dossier. The server reads the API key from the Docker secret `/run/secrets/anthropic_api_key`. It keeps the key and request headers out of its logs, and one of the tests checks the logs for the key. The API, the database tables, and the logging rules are in `server/README.md`.

## Docker containers

Every part of the project runs in a container, and `compose.yaml` defines the containers.

| Container | What it runs | Command |
| --- | --- | --- |
| `app` | The server, which also serves the page, with the database on the `unpackai-data` volume | `scripts/compose-up.sh` |
| `test` | The server tests, with no network access | `docker compose --profile test run --rm --build test` |
| `checks` | The text check and the browser check from the unpack skill, with no network access | `docker compose --profile checks run --rm --build checks` |

Compose copies the page, the skills, and the server code into the images when it builds them. The `--build` option rebuilds the `test` and `checks` images, so the containers check your latest changes. `scripts/compose-up.sh` always rebuilds the `app` image.

The API key reaches the `app` container as the Docker secret `/run/secrets/anthropic_api_key`. The key isn't written to a file on disk, and it isn't set as a variable in the container.

The `app` container is published on 127.0.0.1 only, so other computers can't reach the server. You can pick another port with the `UNPACKAI_PORT` variable, and another Claude model with the `UNPACKAI_MODEL` variable. The default model is `claude-opus-5-5`.

The database stays on the `unpackai-data` volume when you stop or rebuild the containers. The command `docker compose down -v` deletes the volume and every stored dossier.

The `checks` container saves a screenshot of every tab when the repository root has a `shots` folder that anyone can write to, e.g., after `mkdir -p shots && chmod 777 shots`. Add a dossier id after `checks` to save screenshots of only that dossier.

On Windows, run the scripts in WSL or Git Bash. When neither `security` nor `secret-tool` is installed, the scripts use the Python `keyring` package.

If your network inspects TLS traffic with its own certificate, the image builds can't download packages. To fix the builds, build a base image that trusts the certificate and pass it with `--build-arg PYTHON_IMAGE=<image>` for `app` and `test`, or `--build-arg PLAYWRIGHT_IMAGE=<image>` for `checks`.

## Skills

Claude Code and the server both use the skills in `.claude/skills/`, so both of them write dossiers by the same rules.

### Unpack skill

The unpack skill in `.claude/skills/unpack/` has the steps that Claude Code follows for each new unpack request, e.g., "/unpack https://arxiv.org/abs/2312.00752". The skill tells Claude how to pick the paper type, fill in the dossier fields, choose interactive figures from the existing ones, and add the dossier to `index.html`. The server puts the skill in the prompt of its first call.

The skill also has two check scripts, and the `checks` container runs both of them:

- `check_text.py` reports the plain-writing problems that a script can find, e.g., dashes, curly quotes, and sentences that start with a demonstrative pronoun.
- `check_dossiers.js` opens every tab of every dossier in a browser, and it reports script errors, routing problems, and pages that scroll sideways on a phone.

### Plain-writing skill

`CLAUDE.md` requires every paragraph in the project to go through the plain-writing skill, including the paragraphs the app generates. The server uses the skill as the system prompt of its second call.

The plain-writing skill in `.claude/skills/plain-writing/` is copied from [docwriter-org/plain-writing-skill](https://github.com/docwriter-org/plain-writing-skill) at commit `f0d3630`. It is under the MIT license, and the license file is in the same folder.

## Built and planned work

The full app would process each new paper in a fixed order, and the server already does part of the work.

| Step | Status |
| --- | --- |
| Collect new items from arXiv categories (cs.CL and cs.LG) and from the RSS feeds of lab blogs | Planned. The server only takes sources that you send it. |
| Read the sections, tables, figures, and equations | Built in part. Claude reads a PDF from its URL and a blog post with web fetch, and the server doesn't use the LaTeX source from arXiv yet. |
| Fill in the dossier fields, e.g., the new ideas, the claims, and the numbers with their sources | Built. The first call returns the fields as JSON. |
| Compare the paper with earlier dossiers, so reused ideas are marked as inherited | Planned. The first call marks an idea as inherited only when the paper cites earlier work for it. |
| Rewrite every paragraph with the plain-writing skill | Built. The second call rewrites the prose, and the text check runs on the result. |
| Show the dossier in the page, with interactive figures filled in from the paper's numbers | Planned. The first call suggests figures, but the page doesn't read stored dossiers yet. |
