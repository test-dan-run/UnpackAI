# Good dossier text

The examples below come from the FineWeb dossier in `src/web/index.html`. Copy their structure when you write a new dossier, and follow the plain-writing skill for the wording.

## Thesis

The thesis says what the work is in the first sentence and how the authors made their choices in the second sentence. It then names the main new ideas, and each one is in `<span class="mark">` so the page shows it in the color for new ideas. A term that readers may not know gets a short definition, e.g., Common Crawl.

```html
<p class="thesis">FineWeb is an open English web dataset of 15T tokens, built from 96 snapshots of Common Crawl, which is a public archive of web pages. The authors chose each processing step by training small models on the output of the step and comparing their benchmark scores. The main findings are <span class="mark">deduplicating each snapshot on its own instead of across all snapshots</span>, <span class="mark">three new filters chosen from measured page statistics</span>, and <span class="mark">FineWeb-Edu, a subset picked by a classifier trained on scores from Llama-3-70B-Instruct</span>.</p>
```

## Novelty row

A novelty row names the idea, its status, and the practice it replaces. The `why` text gives the paper's evidence, not a general claim, and `where` and `link` point to the tab that explains the idea.

```js
{what:"Deduplicating each snapshot on its own",status:"novel",replaces:"Deduplicating across the whole crawl at once",why:"Deduplicating across all snapshots removed most pages from old snapshots, and the pages that were kept were of lower quality than the pages that were removed. Deduplicating within each snapshot gave better benchmark scores.",where:"Deduplication",link:"#fineweb-dedup"},
```

## What to notice note

A "What to notice" note says what the reader sees in the figure, and then it relates the figure to the paper's result. It also says where the figure can mislead, e.g., when a filter removes a good page.

```html
<p class="notice"><b>What to notice:</b> With the paper's thresholds, the filters remove the menu, the product grid, and the forum page, which have little readable text. The poem is also removed, so the filters can remove some good pages along with many bad pages. In the paper, the three filters together removed about 22% of tokens, and the authors kept the thresholds that improved benchmark scores in their ablations.</p>
```

## Note about something the paper doesn't say

When the paper leaves something out, the dossier says so and doesn't guess. The note below is from the DeepSeek-V3 Data tab, and it states what the report says about attention between documents and what follows from it.

```html
<p class="notice"><b>What to notice:</b> The documents are joined end to end and cut into rows of 4,096 tokens, so no computation is spent on padding. The report says the authors don't mask attention between documents during pre-training. As a result, a token can attend to an unrelated document that comes earlier in the same row.</p>
```

## Claim

A claim has a heading that states the claim, a paragraph that says how the authors tested it, and an evidence label from the table in the unpack skill. The `w` field names the tab with the figure.

```js
{h:"Deduplicating each snapshot on its own gives better models than deduplicating across all snapshots",p:"The authors compared the two methods with ablation models. They also trained a model on the pages that deduplication across all snapshots removed from a 2013 snapshot, and it scored higher than a model trained on the pages that were kept.",ev:"Ablation",c:"ok",w:"Deduplication tab"},
```
