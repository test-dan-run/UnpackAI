// Open every tab of every dossier in src/web/index.html and report problems.
//
// Usage: docker compose --profile checks run --rm --build checks [dossier-id]
// The checks container runs: node check_dossiers.js [screenshot-dir] [dossier-id]
//
// The script opens the page twice in each view. First, it opens the page as a
// file, the way it works without the server. Second, it opens the page from
// the fake server in fake_server.js, the way the app container serves it, and
// it checks the library, the unpack progress, and a stored dossier.
//
// The script reads the dossiers and their tabs from the page, so new dossiers
// are checked without changes here. It reports script errors, tabs that show
// the wrong panel, and pages that scroll sideways at phone width in dark mode.
// With a screenshot folder, it saves a full-page screenshot of each tab of the
// given dossier (or of every dossier) at desktop width and at phone width. The
// checks container writes screenshots to ./shots, which git ignores.
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { ORIGIN, routeFakeServer, imports } = require('./fake_server');

const file_url = 'file://' + path.resolve(__dirname, '../../src/web/index.html');
const [outDir, onlyDoc] = process.argv.slice(2);
const problems = [];

async function openPage(browser, v, label) {
  const page = await browser.newPage({ viewport: { width: v.width, height: 900 }, colorScheme: v.scheme });
  page.on('pageerror', e => problems.push(`${label}: script error: ${e.message}`));
  // A failed load of a web font or other outside file isn't a problem in
  // the page, and the check must also work offline, e.g., in a container
  // with no network. Failed loads of local files and fake server URLs are
  // reported.
  page.on('console', m => { if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) problems.push(`${label}: console error: ${m.text()}`); });
  page.on('requestfailed', r => { if (r.url().startsWith('file:') || r.url().startsWith(ORIGIN)) problems.push(`${label}: can't load ${r.url()}`); });
  return page;
}

async function checkTabs(page, v, label, mode) {
  const docs = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('.doc')]
    .map(d => [d.dataset.doc, [...d.querySelectorAll('.tab')].map(t => t.dataset.tab)])));

  for (const [doc, tabs] of Object.entries(docs)) {
    const panels = await page.evaluate(d => [...document.querySelectorAll(`.doc[data-doc="${d}"] [data-panel]`)].map(s => s.dataset.panel), doc);
    if (panels.join() !== tabs.join()) problems.push(`${label}: ${doc} has tabs [${tabs}] but panels [${panels}]`);
    for (const tab of tabs) {
      await page.evaluate(h => { location.hash = h; }, `#${doc}-${tab}`);
      await page.waitForTimeout(150);
      const shown = await page.evaluate(() => [...document.querySelectorAll('.doc')]
        .filter(d => !d.hidden)
        .map(d => d.dataset.doc + ':' + [...d.querySelectorAll('[data-panel]')].filter(s => !s.hidden).map(s => s.dataset.panel).join(','))
        .join(' '));
      if (shown !== `${doc}:${tab}`) problems.push(`${label}: #${doc}-${tab} shows "${shown}"`);
      const sideways = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      if (sideways && v.name === 'phone') problems.push(`${label}: #${doc}-${tab} scrolls sideways`);
      if (outDir && (!onlyDoc || onlyDoc === doc)) {
        await page.evaluate(() => scrollTo(0, 0));
        await page.screenshot({ path: path.join(outDir, `${v.name}-${mode}-${doc}-${tab}.png`), fullPage: true });
      }
    }
  }
  return docs;
}

// Check that each figure template draws its figure and reacts to its controls.
async function checkFigures(page, v, label) {
  const expect = (ok, what) => { if (!ok) problems.push(`${label}: ${what}`); };
  const fig = '.doc[data-doc="p1"] [data-gen-fig]';
  const drawn = await page.$$eval(`${fig} .gen-fig-body`, els => els.map(e => e.children.length > 0));
  expect(drawn.length === 5 && drawn.every(Boolean), `the page drew [${drawn}] of 5 figures with data`);
  const eyebrows = await page.$$eval(`${fig} .eyebrow`, els => els.map(e => e.textContent));
  expect(eyebrows.filter(t => t === 'Suggested figure, not built yet').length === 1, 'the figure without data isn\'t shown as a suggestion');
  const byTitle = t => page.evaluate(t => [...document.querySelectorAll('.doc[data-doc="p1"] [data-gen-fig]')].find(e => e.querySelector('h3').textContent === t).dataset.genFig, t);
  const read = async (t, sel) => page.evaluate(([i, s]) => (document.querySelector(`.doc[data-doc="p1"] [data-gen-fig="${i}"] ${s}`) || {}).textContent || '', [await byTitle(t), sel]);
  const act = async (t, sel, how) => page.evaluate(([i, s, h]) => {
    const e = document.querySelector(`.doc[data-doc="p1"] [data-gen-fig="${i}"] ${s}`);
    if (h === 'click') e.click(); else { e.value = h; e.dispatchEvent(new Event('input')); }
  }, [await byTitle(t), sel, how]);

  // Comparison: the new method is 400% higher on throughput, and lower is better for perplexity.
  let t = await read('Mamba against Transformers', '.gen-read');
  expect(t.includes('Mamba is 400% higher than'), `the comparison says "${t}"`);
  await act('Mamba against Transformers', '.seg button[data-i="1"]', 'click');
  t = await read('Mamba against Transformers', '.gen-read');
  expect(t.startsWith('Lower values are better for Perplexity.') && t.includes('3.57% lower') && t.includes('so it is better'), `after a metric change, the comparison says "${t}"`);

  // Calculator: 48 layers x 2,048 tokens x 10,240 bytes is 1.007 GB, and 128 times the state.
  t = await read('State size against KV cache size', '.gen-bars');
  expect(t.includes('7.864 MB') && t.includes('1.007 GB'), `the calculator shows "${t}"`);
  t = await read('State size against KV cache size', '.gen-read');
  expect(t === 'Attention KV cache is 128 times Mamba state for these inputs.', `the calculator says "${t}"`);
  await act('State size against KV cache size', 'input[type=range]', '2');
  t = await read('State size against KV cache size', '.gen-bars');
  expect(t.includes('16.11 GB'), `after a context change, the calculator shows "${t}"`);

  // Steps: the Next button moves to step 2, and the share of the first step is shown.
  await act('One step of the selective scan', '[data-move="1"]', 'click');
  t = await read('One step of the selective scan', '.gen-count');
  expect(t === 'Step 2 of 3', `the steps figure counts "${t}"`);
  t = await read('One step of the selective scan', '.gen-step-detail');
  expect(t.includes('which is 50% of the first step'), `the second step says "${t}"`);

  // Timeline: the middle of the slider is in the decay phase.
  t = await read('Learning rate schedule', '.gen-p');
  expect(t === 'Warmup', `the timeline starts in "${t}"`);
  await act('Learning rate schedule', 'input[type=range]', '100');
  t = await read('Learning rate schedule', '.gen-p');
  expect(t === 'Decay', `the middle of the timeline is in "${t}"`);

  // Threshold: 3 of 4 examples are at least 256, and 1 of 4 is at least 4,096.
  t = await read('Filter by sequence length', '.gen-k');
  expect(t === '3 of 4', `the threshold keeps "${t}"`);
  await act('Filter by sequence length', 'input[type=range]', '2');
  t = await read('Filter by sequence length', '.gen-k');
  expect(t === '1 of 4', `after a threshold change, the threshold keeps "${t}"`);
}

async function checkServerViews(page, v, label) {
  const expect = (ok, what) => { if (!ok) problems.push(`${label}: ${what}`); };
  const text = sel => page.evaluate(s => (document.querySelector(s) || {}).textContent || '', sel);

  expect((await text('#apiNote')) === 'Connected to the server', `the header note says "${await text('#apiNote')}"`);
  const statuses = await page.$$eval('#libList .status', els => els.map(e => e.textContent));
  expect(statuses.join() === 'Unpacked,Failed,Unpacking,Unpacked,Sample dossier,Sample dossier,Sample dossier', `the library statuses are [${statuses}]`);

  // The stored dossier escapes the title from the server.
  const h1 = await text('.doc[data-doc="p1"] h1');
  const injected = await page.evaluate(() => !!document.querySelector('.doc[data-doc="p1"] img') || !!window.__xss);
  expect(h1.includes('<img') && !injected, 'the stored dossier doesn\'t escape its title');

  await checkFigures(page, v, label);

  // An idea links to the earlier dossier it came from, and the earlier
  // dossier lists the later papers that reuse its ideas.
  await page.evaluate(() => { location.hash = '#p1-overview'; });
  await page.waitForTimeout(150);
  const links = await page.$$eval('.doc[data-doc="p1"] [data-panel="overview"] .gen-link', els => els.map(e => e.textContent));
  expect(links[0] === 'Builds on "Structured state space layer" in Efficiently Modeling Long Sequences with Structured State Spaces', `the first idea's link says "${links[0]}"`);
  expect((links[1] || '').startsWith('Same idea as'), 'the second idea doesn\'t link to the earlier dossier');
  await page.click('.doc[data-doc="p1"] [data-panel="overview"] .gen-link a');
  await page.waitForTimeout(300);
  const later = await page.$$eval('.doc[data-doc="p4"] [data-panel="overview"] .gaps li', els => els.map(e => e.textContent));
  expect(later.length === 2 && later[0].includes('<img') && later[1].includes('reuses "Structured state space layer"'), `the earlier dossier lists the later ideas as [${later}]`);
  const injectedLater = await page.evaluate(() => !!document.querySelector('.doc[data-doc="p4"] img'));
  expect(!injectedLater, 'the list of later papers doesn\'t escape the title');

  // A dossier from an export file says so, and its link to a paper that
  // isn't in the library shows the title with no link.
  expect((await text('.doc[data-doc="p4"] .ptype-note')).includes('came from an export file'), 'the imported dossier doesn\'t say that it came from an export file');
  expect((await text('.doc[data-doc="p1"] .ptype-note')).includes('The server unpacked the source'), 'the unpacked dossier doesn\'t say that the server unpacked it');
  const missing = await page.$$eval('.doc[data-doc="p4"] .gen-link', els => els.map(e => [e.textContent, !!e.querySelector('a')]));
  expect(missing.length === 1 && missing[0][0] === 'Builds on "HiPPO matrix" in HiPPO: Recurrent Memory with Optimal Polynomial Projections' && !missing[0][1], `the link to a missing paper is [${missing}]`);
  if (outDir && (!onlyDoc || onlyDoc === 'p4')) await page.screenshot({ path: path.join(outDir, `${v.name}-server-p4-later.png`), fullPage: true });

  // Each stored dossier has an export link, and the library has export and import buttons.
  const exportHref = await page.getAttribute('.doc[data-doc="p4"] .gen-share a', 'href');
  expect(exportHref === '/api/papers/4/export', `the export link of p4 is "${exportHref}"`);
  expect(await page.isVisible('#apiShare'), 'the export and import buttons don\'t show');
  expect((await page.getAttribute('#apiShare a', 'href')) === '/api/export', 'the library export link is wrong');
  const file = JSON.stringify({ format: 'unpackai-export', version: 1, papers: [] });
  imports.length = 0;
  await page.setInputFiles('#importFile', { name: 'shared.json', mimeType: 'application/json', buffer: Buffer.from(file) });
  await page.waitForTimeout(300);
  expect(imports.length === 1 && imports[0] === file, 'the import doesn\'t send the file to POST /api/import');
  const imported = await text('#pipelineResult');
  expect(imported.startsWith('Imported 1 paper from shared.json. Skipped 1 paper that was already in the library.'), `the import result says "${imported}"`);
  if (outDir && (!onlyDoc || onlyDoc === 'p4')) await page.screenshot({ path: path.join(outDir, `${v.name}-server-import.png`) });

  // Opening a paper that is still running shows its step.
  await page.click('#libList >> text=Transformers are SSMs');
  await page.waitForTimeout(200);
  expect((await text('#pipelineSteps li.run')).startsWith('Rewrite the prose'), 'the progress view doesn\'t show the plain-writing step');
  if (outDir && (!onlyDoc || onlyDoc === 'p1')) await page.screenshot({ path: path.join(outDir, `${v.name}-server-progress.png`) });

  // A failed paper shows its error and a button that retries it.
  let retried = false;
  page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/api/papers/3/retry')) retried = true; });
  await page.click('#libList >> text=example.com/blog/post');
  await page.waitForTimeout(200);
  expect((await text('#pipelineResult')).includes('invalid x-api-key'), 'the progress view doesn\'t show the error of a failed paper');
  await page.click('#pipelineResult [data-retry]');
  await page.waitForTimeout(200);
  expect(retried, 'the Try again button doesn\'t call the retry endpoint');
}

(async () => {
  const browser = await chromium.launch();
  const views = [
    { name: 'desktop', width: 1400, scheme: 'light' },
    { name: 'phone', width: 400, scheme: 'dark' },
  ];
  if (outDir) fs.mkdirSync(outDir, { recursive: true });

  for (const v of views) {
    let label = `${v.name}, file`;
    let page = await openPage(browser, v, label);
    await page.goto(file_url);
    await page.waitForTimeout(300);
    await checkTabs(page, v, label, 'file');
    if (await page.isVisible('#apiShare')) problems.push(`${label}: the export and import buttons show without a server`);
    await page.close();

    label = `${v.name}, server`;
    page = await openPage(browser, v, label);
    await routeFakeServer(page);
    await page.goto(`${ORIGIN}/#p1-overview`);
    await page.waitForTimeout(500);
    const docs = await checkTabs(page, v, label, 'server');
    if (!docs.p1) problems.push(`${label}: the stored dossier p1 doesn't open`);
    await checkServerViews(page, v, label);
    await page.close();
  }
  await browser.close();
  console.log(problems.length ? problems.join('\n') : 'No problems found');
  process.exit(problems.length ? 1 : 0);
})();
