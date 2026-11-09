# UnpackAI

Unpack new AI research (papers and lab blog posts) into what actually made it work:
the architecture changes, the data curation recipe, and the training loop, each with
interactive visuals.

## Prototype

`index.html` is a self-contained clickable prototype. Open it in a browser; it needs no build step.
It ships with one fully built "dossier" for the **DeepSeek-V3 Technical Report**
(arXiv 2412.19437). The other library entries show how the feed would look.

### Layout

- **Command bar**: paste an arXiv link, blog URL or PDF and press *Unpack*. The prototype
  shows a mock of the extraction pipeline.
- **Library** (left): followed sources, filters by area (Architecture / Data / Training / Systems),
  and the processing status of each item.
- **Dossier** (right): one paper, split into tabs:
  - **Overview**: novelty map. Each idea is tagged *New in this paper*, *Inherited*, or *Standard*,
    with what it replaces, why it works, and the paper section it comes from.
  - **Architecture**: a model map diffed against a plain Transformer, plus three interactive visuals:
    - Router playground: a live simulation of auxiliary-loss-free MoE load balancing.
    - KV-cache calculator comparing MHA, GQA and MLA across context lengths.
    - Multi-token prediction stepper.
  - **Data**: a disclosure scorecard (what the paper reveals vs. withholds), a fill-in-the-middle
    transform demo, and a document-packing visual.
  - **Training loop**: a scrubbable LR / batch-size schedule over 14.8T tokens, the post-training
    stages, a single-step loop walkthrough, and an FP8 per-tensor vs. per-tile quantisation heatmap.
  - **Evidence**: claims tagged by evidence type (ablated, smaller-scale check, self-reported),
    what the paper does not tell you, and a mock "ask the paper" panel with cited answers.

Colour carries meaning throughout: a highlighter yellow for new ideas, blue for inherited ones, grey for standard parts.

## How the real app could work

1. **Ingest**: poll arXiv categories (cs.CL, cs.LG) and lab blog RSS feeds; accept pasted URLs/PDFs.
2. **Parse**: extract sections, tables, figures and equations (e.g. from arXiv LaTeX source when available, else PDF).
3. **Extract**: an LLM fills a structured schema per paper: `novelties[]` (status, replaces, mechanism, section),
   `architecture` (block graph + diffs), `data` (pipeline stages + disclosure flags), `training`
   (schedule, optimiser, stages), `claims[]` (evidence type, section).
4. **Diff against prior work**: cross-reference earlier dossiers so inherited ideas are labelled as such.
5. **Plain-writing pass**: every generated paragraph goes through the plain-writing rules
   (the `/plain-writing` skill) before it is shown. See `CLAUDE.md`.
6. **Pick visuals**: map extracted mechanisms to a library of parameterised visual templates
   (MoE router, attention/KV cache, schedule timeline, data funnel, quantisation, token stepper, etc.).
   Every number shown links back to the paper section it came from.
