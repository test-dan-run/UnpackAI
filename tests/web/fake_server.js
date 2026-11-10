// A fake UnpackAI server for the browser check. Playwright answers every
// request to http://unpackai.test/ from here, so the check can open the page
// the way the app container serves it, with no network and no API key.
//
// The fake server has four papers. Paper 1 is done, and its title holds
// HTML, so the check can test that the page escapes text from the server.
// Its ideas link to the ideas of paper 4, an earlier paper that is also done.
// Paper 1 has one figure for each figure template, and one figure from before
// figure data, which has no data field. Paper 2 is in the plain-writing step, and paper 3 failed. Paper 4 came from
// an export file, and one of its ideas links to a paper that isn't in the
// library, so the link has no paper id.
const fs = require('fs');
const path = require('path');

const INDEX = path.resolve(__dirname, '../../src/web/index.html');
const ORIGIN = 'http://unpackai.test';
const XSS_TITLE = 'Selective state spaces <img src=x onerror="window.__xss=1">';
const S4_TITLE = 'Efficiently Modeling Long Sequences with Structured State Spaces';
const XSS_METHOD = 'Transformer <img src=x onerror="window.__xss=2">';

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
    { what: 'Selection mechanism', status: 'novel', replaces: 'Fixed state space parameters', why: 'The parameters depend on the input.', where: 'architecture',
      earlier: { paper_id: 4, title: S4_TITLE, published: 'Nov 2021', idea: 'Structured state space layer', relation: 'builds_on' } },
    { what: 'Structured state space layer', status: 'inh', replaces: 'Attention', why: 'S4 introduced the layer.', where: 'architecture',
      earlier: { paper_id: 4, title: S4_TITLE, published: 'Nov 2021', idea: 'Structured state space layer', relation: 'same_idea' } },
  ],
  claims: [
    { heading: 'Linear scaling', text: 'Mamba scales linearly in sequence length.', evidence: 'Benchmark', evidence_class: 'ok', where: 'architecture' },
    { heading: 'Language modeling quality', text: 'Mamba-3B matches Transformers twice its size.', evidence: 'Self-reported', evidence_class: 'warn', where: 'evidence' },
  ],
  figures: [
    { tab: 'architecture', kind: 'block_loop_animation', title: 'The scan over the sequence', what_to_notice: 'The scan reads each token once.', uses_made_up_values: true },
    { tab: 'overview', kind: 'method_comparison_simulation', title: 'Mamba against Transformers', what_to_notice: 'Mamba is faster at the same quality.', uses_made_up_values: false,
      data: { template: 'comparison', source: 'Figure 8 and Table 3', metrics: [
        { name: 'Inference throughput', unit: 'tokens/s', higher_is_better: true }, { name: 'Perplexity', unit: '', higher_is_better: false }],
        methods: [{ name: 'Mamba', is_new: true, values: [5000, 8.1] }, { name: XSS_METHOD, is_new: false, values: [1000, 8.4] }, { name: 'Hyena', is_new: false, values: [null, 9.2] }] } },
    { tab: 'architecture', kind: 'memory_calculator', title: 'State size against KV cache size', what_to_notice: 'The state doesn\'t grow with the context.', uses_made_up_values: true,
      data: { template: 'calculator', source: 'Section 3', inputs: [
        { name: 'Layers', unit: '', choices: [48], default_index: 0, from_paper: true },
        { name: 'Context', unit: 'tokens', choices: [2048, 8192, 32768], default_index: 0, from_paper: true },
        { name: 'State size', unit: '', choices: [16], default_index: 0, from_paper: false }],
        outputs: [{ name: 'Mamba state', unit: 'bytes', constant: 10240, powers: [1, 0, 1] }, { name: 'Attention KV cache', unit: 'bytes', constant: 10240, powers: [1, 1, 0] }] } },
    { tab: 'architecture', kind: 'worked_example', title: 'One step of the selective scan', what_to_notice: 'The input sets how much of the state to keep.', uses_made_up_values: false,
      data: { template: 'steps', source: 'Algorithm 2', value_name: 'Numbers read from memory', value_unit: '', steps: [
        { label: 'Load the input', text: 'The kernel loads the input and the parameters into fast memory.', value: 4096, details: [{ label: 'Memory', value: 'SRAM' }] },
        { label: 'Discretize', text: 'The kernel turns the parameters into the discrete form for the step.', value: 2048, details: [] },
        { label: 'Scan', text: 'The kernel runs the scan and writes only the output.', value: 1024, details: [] }] } },
    { tab: 'evidence', kind: 'schedule_timeline', title: 'Learning rate schedule', what_to_notice: 'The rate rises fast and then decays slowly.', uses_made_up_values: false,
      data: { template: 'timeline', source: 'Appendix E', x_name: 'Tokens', x_unit: 'B', y_name: 'Learning rate', y_unit: '', phases: [
        { label: 'Warmup', start: 0, end: 10, start_value: 0, end_value: 0.0006, shape: 'linear' },
        { label: 'Decay', start: 10, end: 300, start_value: 0.0006, end_value: 0.00006, shape: 'cosine' }] } },
    { tab: 'evidence', kind: 'threshold_tester', title: 'Filter by sequence length', what_to_notice: 'A higher threshold keeps fewer examples.', uses_made_up_values: true,
      data: { template: 'threshold', source: 'Section 4.1', score_name: 'Sequence length', keep_when: 'at_least', thresholds: [256, 1024, 4096], default_index: 0, items: [
        { label: 'Short story', score: 300 }, { label: 'Book chapter', score: 5000 }, { label: 'Code file', score: 1200 }, { label: 'Tweet', score: 40 }] } },
  ],
  numbers: [{ value: '5x', meaning: 'Inference throughput compared with Transformers', source: 'Section 4.5' }],
  not_disclosed: ['The exact data mix'],
};

const S4_DOSSIER = {
  paper: { title: S4_TITLE, org: 'Stanford University', published: 'Nov 2021', source_url: 'https://arxiv.org/pdf/2111.00396', paper_type: 'model' },
  thesis: 'S4 is a sequence model built from structured state space layers, which can run as a convolution during training.',
  highlights: ['structured state space layers'],
  specs: [{ value: '16K', label: 'tokens in the longest benchmark task' }],
  tabs: [
    { id: 'overview', title: 'Overview', lede: 'The table lists the new ideas in the paper.' },
    { id: 'evidence', title: 'Evidence', lede: 'Each claim has a tag for the kind of evidence behind it.' },
  ],
  novelties: [
    { what: 'Structured state space layer', status: 'novel', replaces: 'Attention', why: 'The layer has a fast convolution form.', where: 'overview',
      earlier: { paper_id: null, title: 'HiPPO: Recurrent Memory with Optimal Polynomial Projections', published: 'Aug 2020', idea: 'HiPPO matrix', relation: 'builds_on' } },
  ],
  claims: [{ heading: 'Long Range Arena', text: 'S4 solves the Path-X task.', evidence: 'Benchmark', evidence_class: 'ok', where: 'evidence' }],
  figures: [],
  numbers: [],
  not_disclosed: [],
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
  4: { ...base, id: 4, source: 'arxiv:2111.00396', source_kind: 'arxiv', title: S4_TITLE, org: 'Stanford University', published: 'Nov 2021', paper_type: 'model', status: 'done' },
};
const DETAIL = {
  1: { step: 'text_check', calls: CALLS, later: [], dossier: { version: 2, origin: 'unpack', content: DOSSIER, text_problems: [
    { field: 'claims[].text#1', problem: 'overused word (robust)' },
    { field: 'thesis#0', problem: 'em dash' },
  ] } },
  2: { step: 'plain_writing', calls: CALLS.slice(0, 1), later: [], dossier: null },
  3: { step: 'extract', calls: [], later: [], dossier: null },
  4: { step: 'text_check', calls: CALLS, dossier: { version: 1, origin: 'import', content: S4_DOSSIER, text_problems: [] }, later: [
    { paper_id: 1, title: XSS_TITLE, published: 'Dec 2023', idea: 'Selection mechanism', earlier_idea: 'Structured state space layer', relation: 'builds_on' },
    { paper_id: 1, title: XSS_TITLE, published: 'Dec 2023', idea: 'Structured state space layer', earlier_idea: 'Structured state space layer', relation: 'same_idea' },
  ] },
};

const json = (route, status, body, headers) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body), headers });
const EXPORT = papers => ({ format: 'unpackai-export', version: 1, exported_at: '2026-11-10T10:00:00+00:00', papers });
const attachment = name => ({ 'content-disposition': `attachment; filename="${name}"` });
// The check reads the bodies of the import requests from here.
const imports = [];

async function routeFakeServer(page) {
  await page.route(`${ORIGIN}/**`, route => {
    const req = route.request();
    const url = new URL(req.url());
    const m = url.pathname.match(/^\/api\/papers\/(\d+)(\/retry|\/export)?$/);
    if (url.pathname === '/') return route.fulfill({ status: 200, contentType: 'text/html', body: fs.readFileSync(INDEX) });
    if (url.pathname === '/api/health') return json(route, 200, { ok: true, api_key_configured: true });
    if (url.pathname === '/api/papers') return json(route, 200, Object.values(PAPERS).reverse());
    if (url.pathname === '/api/unpack' && req.method() === 'POST') return json(route, 202, { paper_id: 2, queued: false, paper: PAPERS[2] });
    if (url.pathname === '/api/export') return json(route, 200, EXPORT([]), attachment('unpackai-library.json'));
    if (url.pathname === '/api/import' && req.method() === 'POST') {
      imports.push(req.postData());
      return json(route, 200, { added: [{ paper_id: 4, source: PAPERS[4].source, title: S4_TITLE }], skipped: [{ paper_id: 1, source: PAPERS[1].source, title: XSS_TITLE }] });
    }
    if (m && PAPERS[m[1]] && m[2] === '/export') return json(route, 200, EXPORT([]), attachment(`unpackai-paper-${m[1]}.json`));
    if (m && PAPERS[m[1]] && m[2] && req.method() === 'POST') return json(route, 202, { paper_id: +m[1], queued: true, paper: PAPERS[m[1]] });
    if (m && PAPERS[m[1]] && !m[2]) return json(route, 200, { ...PAPERS[m[1]], ...DETAIL[m[1]] });
    return json(route, 404, { detail: 'Not found' });
  });
}

module.exports = { ORIGIN, routeFakeServer, imports };
