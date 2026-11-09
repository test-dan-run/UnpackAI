# UnpackAI

UnpackAI is a web app that explains new AI research papers and lab blog posts. For each paper, it shows the architecture changes, the data preparation, and the training process, and it marks which ideas are new in the paper and which ideas come from earlier work. Interactive figures show how the new ideas work.

## Prototype

The file `index.html` is a clickable prototype, and you can open it in a browser without a build step. The prototype has complete dossiers for three papers, one of each paper type, and the other library entries show how the list of papers would look.

The page has three parts:

- The command bar at the top takes an arXiv link, a blog URL, or a PDF. In the prototype, the Unpack button shows a mock of the processing steps.
- The library on the left lists the papers and posts from the sources you follow. You can filter the library by area, e.g., architecture or data, and each entry shows whether it has been unpacked.
- The dossier on the right explains one paper. It has five tabs:
  - Overview has a table of the paper's ideas, with what each idea replaces, why it works, and the paper section that describes it.
  - Architecture and Training loop have interactive figures, e.g., a simulation of how the router balances work across experts, a KV cache calculator, a learning rate timeline, and an FP8 rounding heatmap.
  - Data shows which parts of the data preparation the paper discloses, with examples of fill-in-the-middle and document packing.
  - Evidence tags each claim by the kind of evidence behind it, e.g., an ablation or a figure the authors report without a separate check.

The colors have a fixed meaning on every page. Yellow marks an idea that is new in the paper, blue marks an idea from earlier work, and grey marks standard practice.

## Paper types

UnpackAI picks the dossier tabs from the type of paper, because each type puts its new ideas in a different place. Every dossier has an Overview tab with the summary table and an Evidence tab with the claims.

| Paper type | Example in the prototype | Tabs between Overview and Evidence |
| --- | --- | --- |
| Model paper | DeepSeek-V3 Technical Report (arXiv 2412.19437) | Architecture, Data, Training loop |
| Dataset paper | The FineWeb Datasets (arXiv 2406.17557) | Pipeline, Filters, Deduplication, FineWeb-Edu |
| Systems paper | FlashAttention (arXiv 2205.14135) | Bottleneck, Algorithm, Performance |

The dataset dossier has a pipeline diagram, a filter tester that computes page statistics from example pages, and a simulation of the two ways to deduplicate across crawl snapshots. Its Evidence tab also lists what the authors released, e.g., the data, the code, and the ablation models.

The systems dossier has a roofline estimate that shows why standard attention is limited by memory traffic, and an animation of the loop over tiles. It also has a worked example of the online softmax and a calculator that compares HBM traffic for standard attention and FlashAttention. Its Performance tab names the baseline for each speedup, because the paper uses different baselines for different results.

## Server

The `server/` folder has a small Python server that makes every call to Claude and stores the results in a SQLite database. It reads the API key from the OS keychain, and it keeps the key and request headers out of its logs. When the server is running, it also serves `index.html` at http://127.0.0.1:8000. The page doesn't call the server yet, so the Unpack button still shows the mock. The setup steps and the API are in `server/README.md`.

## How the full app could work

The full app would process each new paper in a fixed order. First, it collects new items from arXiv categories (cs.CL and cs.LG) and from the RSS feeds of lab blogs, and it accepts URLs and PDFs that a user pastes in. Second, it extracts the sections, tables, figures, and equations, using the LaTeX source from arXiv when it is available and the PDF otherwise. Third, an LLM fills in a fixed set of fields for the paper, e.g., the list of new ideas, the model blocks, the data steps, the training schedule, and the claims with their evidence.

Fourth, the app compares the paper with earlier dossiers, so it can mark reused ideas as inherited. Fifth, every generated paragraph goes through the plain-writing skill before the app shows it, and `CLAUDE.md` has the rule for the project. Sixth, the app picks interactive figure templates that match the extracted ideas, and it fills them with the numbers from the paper. Each number links to the paper section it comes from.

## Unpack skill

The unpack skill in `.claude/skills/unpack/` has the steps that Claude Code follows for each new unpack request, e.g., "/unpack https://arxiv.org/abs/2312.00752". The skill picks the paper type, fills in the dossier fields, chooses interactive figures from the existing ones, and adds the dossier to `index.html`. It also has two check scripts, which you can run on their own:

- `check_text.py` reports the plain-writing problems that a script can find, e.g., dashes, curly quotes, and sentences that start with a demonstrative pronoun.
- `check_dossiers.js` opens every tab of every dossier in a browser, and it reports script errors, routing problems, and pages that scroll sideways on a phone.

## Plain-writing skill

The plain-writing skill in `.claude/skills/plain-writing/` is copied from [docwriter-org/plain-writing-skill](https://github.com/docwriter-org/plain-writing-skill) at commit `f0d3630`. It is under the MIT license, and the license file is in the same folder.
