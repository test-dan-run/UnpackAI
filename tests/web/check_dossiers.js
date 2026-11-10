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
const { ORIGIN, routeFakeServer } = require('./fake_server');

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

async function checkServerViews(page, v, label) {
  const expect = (ok, what) => { if (!ok) problems.push(`${label}: ${what}`); };
  const text = sel => page.evaluate(s => (document.querySelector(s) || {}).textContent || '', sel);

  expect((await text('#apiNote')) === 'Connected to the server', `the header note says "${await text('#apiNote')}"`);
  const statuses = await page.$$eval('#libList .status', els => els.map(e => e.textContent));
  expect(statuses.join() === 'Failed,Unpacking,Unpacked,Sample dossier,Sample dossier,Sample dossier', `the library statuses are [${statuses}]`);

  // The stored dossier escapes the title from the server.
  const h1 = await text('.doc[data-doc="p1"] h1');
  const injected = await page.evaluate(() => !!document.querySelector('.doc[data-doc="p1"] img') || !!window.__xss);
  expect(h1.includes('<img') && !injected, 'the stored dossier doesn\'t escape its title');

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
