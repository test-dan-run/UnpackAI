// Open every tab of every dossier in index.html and report problems.
//
// Usage: docker compose --profile checks run --rm checks [dossier-id]
// The checks container runs: node check_dossiers.js [screenshot-dir] [dossier-id]
//
// The script reads the dossiers and their tabs from the page, so new dossiers
// are checked without changes here. It reports script errors, tabs that show the wrong
// panel, and pages that scroll sideways at phone width in dark mode. With a
// screenshot folder, it saves a full-page screenshot of each tab of the given
// dossier (or of every dossier) at desktop width and at phone width. The
// checks container writes screenshots to ./shots, which git ignores.
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const page_url = 'file://' + path.resolve(__dirname, '../../../../index.html');
const [outDir, onlyDoc] = process.argv.slice(2);

(async () => {
  const browser = await chromium.launch();
  const problems = [];
  const views = [
    { name: 'desktop', width: 1400, scheme: 'light' },
    { name: 'phone', width: 400, scheme: 'dark' },
  ];
  if (outDir) fs.mkdirSync(outDir, { recursive: true });

  for (const v of views) {
    const page = await browser.newPage({ viewport: { width: v.width, height: 900 }, colorScheme: v.scheme });
    page.on('pageerror', e => problems.push(`${v.name}: script error: ${e.message}`));
    // A failed load of a web font or other outside file isn't a problem in
    // the page, and the check must also work offline, e.g., in a container
    // with no network. Failed loads of local files are reported.
    page.on('console', m => { if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) problems.push(`${v.name}: console error: ${m.text()}`); });
    page.on('requestfailed', r => { if (r.url().startsWith('file:')) problems.push(`${v.name}: can't load ${r.url()}`); });
    await page.goto(page_url);
    await page.waitForTimeout(300);

    const docs = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('.doc')]
      .map(d => [d.dataset.doc, [...d.querySelectorAll('.tab')].map(t => t.dataset.tab)])));

    for (const [doc, tabs] of Object.entries(docs)) {
      const panels = await page.evaluate(d => [...document.querySelectorAll(`.doc[data-doc="${d}"] [data-panel]`)].map(s => s.dataset.panel), doc);
      if (panels.join() !== tabs.join()) problems.push(`${v.name}: ${doc} has tabs [${tabs}] but panels [${panels}]`);
      for (const tab of tabs) {
        await page.evaluate(h => { location.hash = h; }, `#${doc}-${tab}`);
        await page.waitForTimeout(150);
        const shown = await page.evaluate(() => [...document.querySelectorAll('.doc')]
          .filter(d => !d.hidden)
          .map(d => d.dataset.doc + ':' + [...d.querySelectorAll('[data-panel]')].filter(s => !s.hidden).map(s => s.dataset.panel).join(','))
          .join(' '));
        if (shown !== `${doc}:${tab}`) problems.push(`${v.name}: #${doc}-${tab} shows "${shown}"`);
        const sideways = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
        if (sideways && v.name === 'phone') problems.push(`phone: #${doc}-${tab} scrolls sideways`);
        if (outDir && (!onlyDoc || onlyDoc === doc)) {
          await page.evaluate(() => scrollTo(0, 0));
          await page.screenshot({ path: path.join(outDir, `${v.name}-${doc}-${tab}.png`), fullPage: true });
        }
      }
    }
    await page.close();
  }
  await browser.close();
  console.log(problems.length ? problems.join('\n') : 'No problems found');
  process.exit(problems.length ? 1 : 0);
})();
