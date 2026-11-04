/* Real browser reproduction. Never writes session tokens or Authorization headers. */
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.MOLCHAT_PLAYWRIGHT_MODULE || 'playwright-core');
const args = process.argv.slice(2);
const option = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const url = option('--url', 'http://localhost:13016/');
if (!['localhost', '127.0.0.1'].includes(new URL(url).hostname)) throw Error('A local test capsule is required.');
const output = path.resolve(option('--output', 'reports/capsule-reproduction'));
const caseName = option('--case', 'benchmark-vmat2-' + new Date().toISOString().replace(/[^0-9]/g, '').slice(0, 14));
const prompt = `Prepare an approved-once iteration in a NEW case called ${caseName}. Resolve aspirin, ketanserin and valbenazine through PubChem in exactly that order. Receptor VMAT2, PDB 8T69. Stop at the FIRST candidate with Vina energy <= -10.5 kcal/mol AND passed physical pose checks. Save the selected run in Moldex, make a short preview search video, audit it in Preparation, and deliver the notebook, original Preparation package and video in a single ZIP. First show the approval card and wait; do not start docking yet.`;
const decode = body => {
  try {
    if (body.split('\n').some(line => line.startsWith('data:'))) return body.split('\n').filter(line => line.startsWith('data:')).map(line => JSON.parse(line.slice(5)));
    return JSON.parse(body);
  } catch { return body; }
};
const safeJSON = value => JSON.stringify(value, (key, item) => key === 'paths' ? undefined : item, 2)
  .replace(/[A-Za-z]:[\\/]+/g, '[local-path]/') + '\n';

(async () => {
  await fs.mkdir(path.join(output, 'screenshots'), { recursive: true });
  const executablePath = process.env.MOLCHAT_BROWSER_EXECUTABLE ||
    path.join(process.env['ProgramFiles(x86)'] || process.env.ProgramFiles, 'Microsoft/Edge/Application/msedge.exe');
  const browser = await chromium.launch({ executablePath, headless: true });
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 }, locale: 'en-US' });
  const page = await context.newPage();
  const record = { schema: 'molchat.capsule-run/1', started_at_utc: new Date().toISOString(),
                   prompt, requests: [], responses: [], assertions: [] };
  const pending = [];
  let session;
  const check = (name, actual, expected) => {
    record.assertions.push({ name, actual, expected, passed: JSON.stringify(actual) === JSON.stringify(expected) });
    assert.deepEqual(actual, expected, name);
  };
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /^(Open MolChat|Abrir MolChat)/ }).first().click({ timeout: 60000 });
    const frame = page.frameLocator('iframe');
    await frame.getByPlaceholder(/scientific question|pregunta científica/).waitFor({ timeout: 90000 });
    const auth = await page.evaluate(() => JSON.parse(localStorage.getItem('moldesign_auth')));
    const backend = option('--backend', 'http://127.0.0.1:18016');
    if (!['localhost', '127.0.0.1'].includes(new URL(backend).hostname)) throw Error('A local backend is required.');
    const response = await context.request.post(backend + '/molchat-host/session', { headers: { Authorization: 'Bearer ' + auth.token } });
    assert(response.ok(), 'MolDesign must authorize a new sidecar session');
    session = await response.json();
    const status = await (await context.request.get(backend + '/molchat-host/status')).json();
    record.sidecar = status;
    page.on('request', request => {
      const u = new URL(request.url());
      if (u.origin === session.url && request.method() === 'POST') record.requests.push({ path: u.pathname, time_utc: new Date().toISOString(), body: decode(request.postData() || '{}') });
    });
    page.on('response', response => {
      const u = new URL(response.url());
      if (u.origin !== session.url || !(u.pathname === '/v1/chat' || u.pathname.includes('/v1/workflows/'))) return;
      pending.push(response.text().then(body => record.responses.push({ path: u.pathname, status: response.status(), body: decode(body) })).catch(() => {}));
    });
    await frame.getByRole('button', { name: /^(New conversation|Nueva conversación)$/ }).click();
    await frame.getByPlaceholder(/scientific question|pregunta científica/).fill(prompt);
    const chatResponse = page.waitForResponse(r => r.url() === session.url + '/v1/chat', { timeout: 180000 });
    await frame.getByRole('button', { name: /^(Send|Enviar)$/ }).click();
    const events = decode(await (await chatResponse).text());
    const result = events.find(e => e.type === 'result')?.result;
    assert(result, 'The model must finish the turn');
    check('exactly one workflow card', result.workflow_proposals.length, 1);
    const card = result.workflow_proposals[0];
    record.card = card;
    check('candidate order', card.molecules.map(m => m.toLowerCase()), ['aspirin', 'ketanserin', 'valbenazine']);
    check('no host mutation before approval', record.requests.filter(r => /\/(case|smiles|receptor|evaluation)-requests\//.test(r.path)).length, 0);
    const denied = await context.request.post(`${session.url}/v1/workflows/${card.id}/run`, {
      headers: { Authorization: 'Bearer ' + session.token }, data: { digest: 'sha256:deliberately-wrong-benchmark' } });
    check('wrong digest rejected', denied.status(), 409);
    const approve = frame.getByRole('button', { name: /^(Approve and run|Aprobar y ejecutar)$/ });
    await approve.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'screenshots/01-approval.png') });
    record.approved_at_utc = new Date().toISOString();
    await approve.click();
    console.log('Approved: real docking campaign started.');
    let captured = false;
    const deadline = Date.now() + 15 * 60 * 1000;
    while (Date.now() < deadline) {
      const response = await context.request.get(`${session.url}/v1/workflows/${card.id}`, { headers: { Authorization: 'Bearer ' + session.token } });
      record.latest = await response.json();
      if (!captured && record.requests.some(r => r.path.includes('/evaluation-requests/'))) {
        await page.screenshot({ path: path.join(output, 'screenshots/02-running.png') });
        captured = true;
      }
      if (record.latest.state === 'done' && !record.latest.summary?.video_pending) break;
      await new Promise(resolve => setTimeout(resolve, 3000));
    }
    check('workflow finished', record.latest.state, 'done');
    check('video finished', record.latest.summary.video, 'completo');
    check('stopping counts', record.latest.summary.counts, { evaluated: 2, skipped: 1 });
    check('selected candidate', record.latest.summary.selected.name.toLowerCase(), 'ketanserin');
    check('selected physical checks', record.latest.summary.selected.physical_status, 'passed');
    check('Moldex saved', record.latest.summary.saved, 'saved');
    check('Preparation verdict preserved', record.latest.summary.preparation, 'REVIEW');
    await frame.locator('.iteration-table').screenshot({ path: path.join(output, 'screenshots/03-stop.png') });
    for (const [apiName, name] of [['entrega.zip', 'delivery.zip'], ['cuaderno.md', 'notebook.md'], ['cuaderno.json', 'notebook.json'], ['cuaderno.pdf', 'notebook.pdf']]) {
      const response = await context.request.get(`${session.url}/v1/workflows/${card.id}/files/${apiName}`, { headers: { Authorization: 'Bearer ' + session.token } });
      assert(response.ok(), 'Output must be downloadable');
      await fs.writeFile(path.join(output, name), await response.body());
    }
    const before = record.requests.filter(r => r.path.includes('/evaluation-requests/')).length;
    const again = await context.request.post(`${session.url}/v1/workflows/${card.id}/run`, { headers: { Authorization: 'Bearer ' + session.token }, data: { digest: card.digest } });
    check('repeat approval is a result read', again.status(), 200);
    check('repeat approval dispatches no extra evaluation', record.requests.filter(r => r.path.includes('/evaluation-requests/')).length, before);
    record.finished_at_utc = new Date().toISOString();
    record.passed = true;
    console.log('Completed: original notebook, ZIP and video downloaded.');
  } catch (error) {
    record.passed = false;
    record.error = String(error);
    process.exitCode = 1;
    console.error(String(error));
  } finally {
    await Promise.allSettled(pending);
    await fs.writeFile(path.join(output, 'execution.json'), safeJSON(record));
    session = undefined;
    await context.close();
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
