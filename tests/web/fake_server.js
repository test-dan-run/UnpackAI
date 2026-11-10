// A fake UnpackAI server for the browser check. Playwright answers every
// request to http://unpackai.test/ from here, so the check can open the page
// the way the app container serves it, with no network and no API key.
//
// The fake server has three papers. Paper 1 is done, and its title holds
// HTML, so the check can test that the page escapes text from the server.
// Paper 2 is in the plain-writing step, and paper 3 failed.
const fs = require('fs');
const path = require('path');

const INDEX = path.resolve(__dirname, '../../src/web/index.html');
const ORIGIN = 'http://unpackai.test';
const XSS_TITLE = 'Selective state spaces <img src=x onerror="window.__xss=1">';

const DOSSIER = {
  paper: { title: XSS_TITLE, org: 'CMU and Princeton', published: 'Dec 2023', source_url: 'https://arxiv.org/pdf/2312.00752', paper_type: 'model' },
  thesis: 'Mamba is a sequence model that uses selective state spaces instead of attention, so its cost grows in a straight line with the sequence length.',
  highlights: ['selective state spaces'],
  specs: [{ value: '5x', label: 'higher inference throughput than Transformers' }, { value: '2.8B', label: 'parameters in the largest model' }],
  tabs: [
    { id: 'overview', title: 'Overview', lede: 'The table lists the new ideas in the paper.' },
    { id: 'architecture', title: 'Architecture', lede: 'The Mamba block replaces the attention block.' },
    { id: 'evidence', title: 'Evidence', lede: 'Each claim has a tag for the kind of evidence behind it.' },
  ],
  novelties: [
    { what: 'Selection mechanism', status: 'novel', replaces: 'Fixed state space parameters', why: 'The parameters depend on the input.', where: 'architecture' },
    { what: 'Structured state space layer', status: 'inh', replaces: 'Attention', why: 'S4 introduced the layer.', where: 'architecture' },
  ],
  claims: [
    { heading: 'Linear scaling', text: 'Mamba scales linearly in sequence length.', evidence: 'Benchmark', evidence_class: 'ok', where: 'architecture' },
    { heading: 'Language modeling quality', text: 'Mamba-3B matches Transformers twice its size.', evidence: 'Self-reported', evidence_class: 'warn', where: 'evidence' },
  ],
  figures: [
    { tab: 'architecture', kind: 'block_loop_animation', title: 'The scan over the sequence', what_to_notice: 'The scan reads each token once.', uses_made_up_values: true },
  ],
  numbers: [{ value: '5x', meaning: 'Inference throughput compared with Transformers', source: 'Section 4.5' }],
  not_disclosed: ['The exact data mix'],
};

const CALLS = [
  { step: 'extract', model: 'claude-opus-5-5', stop_reason: 'end_turn', input_tokens: 41000, output_tokens: 6100, duration_ms: 95000, error: null, created_at: '2026-11-10T10:00:00+00:00' },
  { step: 'plain_writing', model: 'claude-opus-5-5', stop_reason: 'end_turn', input_tokens: 9000, output_tokens: 5800, duration_ms: 61000, error: null, created_at: '2026-11-10T10:02:00+00:00' },
];

const base = { org: null, published: null, paper_type: null, error: null, created_at: '2026-11-10T10:00:00+00:00', updated_at: '2026-11-10T10:00:00+00:00' };
const PAPERS = {
  1: { ...base, id: 1, source: 'arxiv:2312.00752', source_kind: 'arxiv', title: XSS_TITLE, org: 'CMU and Princeton', published: 'Dec 2023', paper_type: 'model', status: 'done' },
  2: { ...base, id: 2, source: 'arxiv:2405.21060', source_kind: 'arxiv', title: 'Transformers are SSMs', org: 'Princeton and CMU', published: 'May 2024', paper_type: 'model', status: 'running' },
  3: { ...base, id: 3, source: 'https://example.com/blog/post', source_kind: 'web_url', status: 'failed', error: 'Claude API error 401 (AuthenticationError): invalid x-api-key' },
};
const DETAIL = {
  1: { step: 'text_check', calls: CALLS, dossier: { version: 2, content: DOSSIER, text_problems: [
    { field: 'claims[].text#1', problem: 'overused word (robust)' },
    { field: 'thesis#0', problem: 'em dash' },
  ] } },
  2: { step: 'plain_writing', calls: CALLS.slice(0, 1), dossier: null },
  3: { step: 'extract', calls: [], dossier: null },
};

const json = (route, status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

async function routeFakeServer(page) {
  await page.route(`${ORIGIN}/**`, route => {
    const req = route.request();
    const url = new URL(req.url());
    const m = url.pathname.match(/^\/api\/papers\/(\d+)(\/retry)?$/);
    if (url.pathname === '/') return route.fulfill({ status: 200, contentType: 'text/html', body: fs.readFileSync(INDEX) });
    if (url.pathname === '/api/health') return json(route, 200, { ok: true, api_key_configured: true });
    if (url.pathname === '/api/papers') return json(route, 200, Object.values(PAPERS).reverse());
    if (url.pathname === '/api/unpack' && req.method() === 'POST') return json(route, 202, { paper_id: 2, queued: false, paper: PAPERS[2] });
    if (m && PAPERS[m[1]] && m[2] && req.method() === 'POST') return json(route, 202, { paper_id: +m[1], queued: true, paper: PAPERS[m[1]] });
    if (m && PAPERS[m[1]] && !m[2]) return json(route, 200, { ...PAPERS[m[1]], ...DETAIL[m[1]] });
    return json(route, 404, { detail: 'Not found' });
  });
}

module.exports = { ORIGIN, routeFakeServer };
