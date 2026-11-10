# ADR 014: Stored dossiers draw their figures from templates

Status: Accepted

Date: 2026-11-10

## Context

The sample dossiers have interactive figures that a person or Claude Code wrote by hand in `src/web/index.html`. Before the change, a dossier that the server unpacked listed the figures that the extract call suggested, with a title and a "What to notice" note, but the page didn't draw them. The text in a stored dossier comes from a paper or a web page, and an export file can come from another person, so the page escapes every value from the server (ADR 011 and ADR 013). Every number in a figure has to come from the paper, or the figure has to say that it uses example values.

## Options

1. Ask Claude to write the HTML and the script of each figure, and add the code to the page
2. Give the page a fixed set of figure templates, and ask Claude for the numbers and the labels that fill each template
3. Keep the suggested figures without drawing them

## Decision

UnpackAI uses option 2. The extract call fills a `data` field for each figure with one of five templates, and it sets the field to null when no template fits. `FIGURE_TEMPLATES` in `dossier_schema.py` defines the templates, and `GEN_FIG` in the page draws them.

| Template | What the reader can do | Fits figures like |
| --- | --- | --- |
| `comparison` | Pick a metric, and see a bar for each method and how the new method compares with the best other method | Benchmark results |
| `calculator` | Move a slider for each input, and see each output, which is a constant times each input raised to a power | Memory, cache, and cost estimates |
| `timeline` | Move a slider over time, and see the value and the phase | Learning rate schedules and training stages |
| `steps` | Move through the steps, and see the text, a value, and the details of each step | Pipelines and calculations done step by step |
| `threshold` | Move a threshold, and see which example items are kept | Filters that keep or drop data |

The data holds only numbers and short labels, plus the text of each step, which goes through the plain-writing call. The server checks the data with `clean_figures()` after the extract call and on import, e.g., that each method has one value for each metric and that each power is between -4 and 4. It sets data that the page couldn't draw to null, so the figure falls back to its title and its note, and the unpack doesn't fail.

## Consequences

- The page runs no code from Claude or from an export file, so a figure can't add a script to the page.
- The page computes each output from the inputs, so the numbers stay correct when the reader moves a control.
- Five templates can't show every idea, e.g., a router simulation or a number format heatmap. A figure that no template fits keeps its title and its note, and a new kind of figure needs a new template in the schema, the page, the fake server, and the tests.
- The extract call returns more JSON, so it costs more output tokens.
- Export files moved to version 2, because each figure now has a `data` field. The server still reads version 1 files, and their figures have no data.
- The dossiers that the server stored before the change have figures without data, and they keep showing the title and the note until the paper is unpacked again.
