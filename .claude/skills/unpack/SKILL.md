---
name: unpack
description: Unpacks a new AI research paper or lab blog post into a dossier in the UnpackAI prototype (src/web/index.html). Use for every unpack request, e.g., "/unpack <arXiv link>", "unpack this paper", "add a dossier for <paper>", or a pasted arXiv link, blog URL, or PDF with a request to explain it in UnpackAI. Don't use it for layout changes to the app that don't add a paper.
---

# Unpack a paper into a dossier

An unpack request asks for a new dossier in `src/web/index.html` for one paper or blog post. The dossier explains what is new in the work and what the work reuses from earlier work, and it shows how well the evidence supports each claim. Work through the four stages below in order, and don't skip the checks in the last stage.

## Before you start

Load the `/plain-writing` skill, because `CLAUDE.md` requires it for every paragraph in a dossier. If the skill doesn't load, tell the user and stop.

Read `AGENTS.md`, the page section of `docs/repository-map.md`, and the examples in `docs/examples/`. Then read the existing dossier that is closest to the new paper, because the new dossier copies its structure. The prototype has one example of each paper type:

- DeepSeek-V3 (`data-doc="dsv3"`) is the model paper.
- FineWeb (`data-doc="fineweb"`) is the dataset paper.
- FlashAttention (`data-doc="flash"`) is the systems paper.

## Stage 1. Read the source

1. Get the full text of the work.
   - For an arXiv paper, download the LaTeX source from `https://arxiv.org/e-print/<id>` if it exists, because the source has the exact tables and equations. Otherwise, read the PDF.
   - For a blog post, read the page with the web-fetch agent, and also read the paper or code that the post links to.
   - If you can't get the full text, tell the user. Don't write a dossier from the abstract alone.
2. Write down the metadata, which is the title, the arXiv id or URL, the month and year, and the organization.
3. Make a list of every number you plan to use, with the section, table, or figure it comes from. Every number in the dossier must come from the list.
4. Make a list of what the work doesn't disclose, e.g., the data mix or the hyperparameters. The dossier states each missing item, and it doesn't guess the value.

## Stage 2. Plan the dossier

### Pick the paper type

The paper type sets the tabs, because each type puts its new ideas in a different place. Every dossier starts with an Overview tab and ends with an Evidence tab.

| Paper type | How to recognize it | Tabs between Overview and Evidence |
| --- | --- | --- |
| Model paper | The work describes a trained model and how it was built | Architecture, Data, Training loop |
| Dataset paper | The main result is a dataset or a data processing pipeline | Pipeline, Filters, Deduplication, and one tab for the main subset or classifier |
| Systems paper | The main result is faster or cheaper training or inference with the same output | Bottleneck, Algorithm, Performance |

If the work fits none of the types, e.g., a benchmark paper or a new RL method, choose three or four tabs by the same rule. Each tab covers one part of the work that contains new ideas, and you tell the user which tabs you chose and why.

### Fill in the fields

Each dossier has the same fields, and the shared helpers in the script turn the fields into HTML.

- The paper head has these parts:
  - An eyebrow line with the paper type, the link, the date, and the organization
  - A thesis paragraph that says what the work is, with each main new idea in `<span class="mark">`
  - Six specs, which are the six numbers a reader needs first, e.g., parameter count or token count
  - A `ptype-note` that names the paper type and the tabs it adds
- The novelty rows go in a `<PREFIX>_NOVEL` array for `noveltyRows()`. Each row has `what`, `status`, `replaces`, `why`, `where`, and `link`.
- The claims go to `claimsHTML()`. Each claim has a heading `h`, a paragraph `p`, an evidence label `ev`, a class `c`, and an optional `w` that names the tab with the figure.
- Each tab has one or two figures and a short lede paragraph.

### Mark each idea as new, inherited, or standard

The `status` field uses three values, and the colors on the page depend on them.

- Use `novel` when the paper presents the idea as its own and cites no earlier source for it.
- Use `inh` when the paper cites earlier work for the idea, or when an earlier dossier in the prototype has the same idea. Name the earlier work in the `why` text.
- Use `std` when the idea is common practice and the paper doesn't claim it.

If you can't tell whether an idea is new, mark it `inh` and say in the `why` text what the paper cites.

### Tag the evidence for each claim

Use the evidence labels that the existing dossiers already use, so readers can compare dossiers.

| `ev` label | `c` class | When to use it |
| --- | --- | --- |
| Ablation | `ok` | The authors compared runs with and without the idea |
| Proof | `ok` | The paper proves the claim, e.g., a bound on memory traffic |
| Benchmark | `ok` | The authors measured the result against a named baseline |
| Checked on smaller models | `warn` | The authors tested the idea only at a smaller scale than the final model |
| Checked against LLM scores | `warn` | The only check is agreement with scores from another model |
| Self-reported | `std` | The paper reports a figure without a separate check, e.g., cost in GPU hours |

You can add a more exact label, e.g., "Benchmark against a published record", if it keeps one of the three classes.

### Choose the interactive figures

Each figure shows how one new idea works, so the reader can change an input and see the effect. Reuse an existing figure when the idea is of the same kind.

| Kind of idea | Existing figure to start from |
| --- | --- |
| Routing or load balancing | The router simulation in the DeepSeek-V3 Architecture tab |
| Memory or cache size | The KV cache calculator in the DeepSeek-V3 Architecture tab |
| Schedules and training stages | The learning rate timeline in the DeepSeek-V3 Training loop tab |
| Number formats and rounding | The FP8 heatmap in the DeepSeek-V3 Training loop tab |
| A sequence of processing steps | The pipeline diagram in the FineWeb Pipeline tab |
| Thresholds that keep or drop data | The filter tester in the FineWeb Filters tab |
| A choice between two data methods | The deduplication simulation in the FineWeb Deduplication tab |
| Speed limited by memory traffic | The roofline estimate in the FlashAttention Bottleneck tab |
| A loop over blocks of data | The tiling animation in the FlashAttention Algorithm tab |
| A calculation done step by step | The online softmax example in the FlashAttention Algorithm tab |

Each figure follows these rules:

1. The figure uses the paper's numbers. If the figure needs values that the paper doesn't give, write example values and add a `<p class="proto-note">` that says which values are made up.
2. The figure computes its output from its inputs, e.g., page statistics from the page text, so the output stays correct when the reader moves a control. Check one output by hand against the paper.
3. The figure has a `<p class="notice"><b>What to notice:</b> ...</p>` note that says what the reader should look for and how it relates to the paper's result.
4. The figure has an `aria-label` on each SVG and on each group of buttons.

## Stage 3. Build the dossier

Pick a short id of lowercase letters for the dossier, e.g., `mamba`, and a two-letter prefix for the script, e.g., `MB`. All the dossiers share one page and one script, so put the prefix on every element id and every top-level name, e.g., `mbRows` and `MB_NOVEL`. If two `const` declarations share a name, the browser reports a syntax error and runs none of the script.

1. Add the HTML.
   - Add `<div class="doc" data-doc="<id>" hidden>` inside `<main class="dossier" id="dossier">`, after the last dossier.
   - Copy the paper head, the `nav.tabs`, and one `section.panel[data-panel]` per tab from the closest example. Each tab links to `#<id>-<tab>`, and every panel except Overview has `hidden`.
2. Connect the dossier to the library and the router.
   - In `LIB`, add an entry with `ready:true` and `built:true`, or add `built:true` to the entry if it's already there, e.g., Mamba, DeepSeek-R1, and DataComp-LM.
   - Add the paper's short name to the toast text in `renderLib()`, which lists the dossiers that the prototype has.
   - Add the id and its tab list to `DOCS`, and add the id to the regular expression in `parseHash()`.
3. Add the script in a new block after the last dossier block, with a comment line that names the paper. Use the shared helpers `noveltyRows()`, `claimsHTML()`, `detailHTML()`, and `makeSeg()`.
4. Reuse the existing CSS classes. Add new rules only when no class fits, and put them before `@media (max-width:1100px)` with a rule for 620px and less. Use the color tokens, e.g., `--hl`, `--inh`, `--std`, `--ink`, and `--paper`, so the colors work in dark mode.

## Stage 4. Check and ship

1. Read every paragraph you added against the plain-writing skill, e.g., the thesis, the novelty rows, the "What to notice" notes, and the claims.
2. Run the checks container from the repository root.
   - Create the screenshot folder with `mkdir -p shots && chmod 777 shots`, because the container's user must be able to write to it. Git ignores the folder.
   - Run `docker compose --profile checks run --rm --build checks <id>`. The `--build` option copies your changes into the image, and `<id>` limits the screenshots to the new dossier.
   - The container first runs `src/server/unpackai_server/text_check.py` on the page and the documentation. The script checks the rules that a script can check, e.g., dashes and curly quotes. The container then runs `tests/web/check_dossiers.js`, which opens every tab of every dossier and reports script errors, tabs that show the wrong panel, and pages that scroll sideways on a phone. Fix every problem the checks report.
   - Look at the screenshots of the new dossier at desktop width and at phone width, and use each interactive control once.
3. Update the documentation.
   - In `docs/architecture.md`, add the dossier to the "Dossier structure" section, with a short paragraph about its figures.
   - If the paper type is new, add a row to the paper type tables in `docs/architecture.md` and in the "Pick the paper type" section of the skill.
   - If the dossier has a new kind of figure, add a row to the figure table in the skill.
4. Commit the change, and push it to the working branch. If the user has published the prototype as an artifact, publish the new version to the same URL.

## Reply to the user

The reply follows the plain-writing skill, and it covers the following points:

- The paper type and the tabs, with the reason for any tab that is new
- The interactive figures and what each one shows
- Which values in the dossier are made up for the demo
- What the work doesn't disclose, and anything you couldn't check
