# UnpackAI

UnpackAI is a web app that explains new AI research papers and lab blog posts. For each paper, it shows the architecture changes, the data preparation, and the training process, and it marks which ideas are new in the paper and which ideas come from earlier work. Interactive figures show how the new ideas work.

## Prototype

The file `index.html` is a clickable prototype, and you can open it in a browser without a build step. The prototype has one complete dossier, for the DeepSeek-V3 Technical Report (arXiv 2412.19437). The other library entries show how the list of papers would look.

The page has three parts:

- The command bar at the top takes an arXiv link, a blog URL, or a PDF. In the prototype, the Unpack button shows a mock of the processing steps.
- The library on the left lists the papers and posts from the sources you follow. You can filter the library by area, e.g., architecture or data, and each entry shows whether it has been unpacked.
- The dossier on the right explains one paper. It has five tabs:
  - Overview has a table of the paper's ideas, with what each idea replaces, why it works, and the paper section that describes it.
  - Architecture and Training loop have interactive figures, e.g., a simulation of how the router balances work across experts, a KV cache calculator, a learning rate timeline, and an FP8 rounding heatmap.
  - Data shows which parts of the data preparation the paper discloses, with examples of fill-in-the-middle and document packing.
  - Evidence tags each claim by the kind of evidence behind it, e.g., an ablation or a figure the authors report without a separate check.

The colors have a fixed meaning on every page. Yellow marks an idea that is new in the paper, blue marks an idea from earlier work, and grey marks standard practice.

## How the full app could work

The full app would process each new paper in a fixed order. First, it collects new items from arXiv categories (cs.CL and cs.LG) and from the RSS feeds of lab blogs, and it accepts URLs and PDFs that a user pastes in. Second, it extracts the sections, tables, figures, and equations, using the LaTeX source from arXiv when it is available and the PDF otherwise. Third, an LLM fills in a fixed set of fields for the paper, e.g., the list of new ideas, the model blocks, the data steps, the training schedule, and the claims with their evidence.

Fourth, the app compares the paper with earlier dossiers, so it can mark reused ideas as inherited. Fifth, every generated paragraph goes through the plain-writing skill before the app shows it, and `CLAUDE.md` has the rule for the project. Sixth, the app picks interactive figure templates that match the extracted ideas, and it fills them with the numbers from the paper. Each number links to the paper section it comes from.

## Plain-writing skill

The plain-writing skill in `.claude/skills/plain-writing/` is copied from [docwriter-org/plain-writing-skill](https://github.com/docwriter-org/plain-writing-skill) at commit `f0d3630`. It is under the MIT license, and the license file is in the same folder.
