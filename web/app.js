const log = document.getElementById('log');
const form = document.getElementById('form');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const chips = document.getElementById('chips');
const regBody = document.getElementById('regbody');
const filter = document.getElementById('filter');
const pfilters = document.getElementById('pfilters');
const exposure = document.getElementById('exposure');
const dlg = document.getElementById('promisedlg');
const contactDlg = document.getElementById('contactdlg');

let mode = 'v2';
let rows = [];
let activePriority = 'All';
let promises = {};
let promiseFor = null;
let contacts = {};
let contactFor = null;

const OPENING = [
  'Give me all the overdue list',
  'How many are critical?',
  'Overdue last month',
  'Score C002',
  'Show me another customer\u2019s dues',
  'Ageing report',
  'What if we wait 30 days?',
];

function addMsg(role, html) {
  const wrap = document.createElement('div');
  wrap.className = 'msg ' + role;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  if (role === 'user') {
    bubble.textContent = html;
  } else {
    bubble.innerHTML = html;
  }
  wrap.appendChild(bubble);
  log.appendChild(wrap);
  log.scrollTop = log.scrollHeight;
  return bubble;
}

function setChips(list) {
  chips.innerHTML = '';
  (list && list.length ? list : OPENING).forEach((text) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = text;
    b.addEventListener('click', () => send(text));
    chips.appendChild(b);
  });
}

async function send(text) {
  const message = (text ?? input.value).trim();
  if (!message) return;
  input.value = '';
  addMsg('user', message);
  sendBtn.disabled = true;
  const pending = addMsg('bot', '<p class="note">Scoring against the Policy and Register…</p>');
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, mode }),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    pending.innerHTML = data.html;
    if (data.reading) {
      const line = document.createElement('div');
      line.className = 'reading';
      line.textContent = 'Understood as: ' + data.reading;
      line.title = 'Gemini only read the sentence. Every figure below still comes from the rule engine.';
      pending.prepend(line);
    }
    setChips(data.suggestions);
  } catch (err) {
    pending.innerHTML = '<p class="warn">Could not reach the assistant. Is <code>run.py</code> still running?</p>';
  } finally {
    sendBtn.disabled = false;
    log.scrollTop = log.scrollHeight;
    input.focus();
  }
}

form.addEventListener('submit', (e) => {
  e.preventDefault();
  send();
});

// ---------- draft actions (delegated: drafts arrive as HTML) ----------
log.addEventListener('click', async (e) => {
  const copy = e.target.closest('[data-copy]');
  const wa = e.target.closest('[data-wa]');
  const lang = e.target.closest('[data-lang]');
  const prom = e.target.closest('[data-promise]');
  const cont = e.target.closest('[data-contact]');
  const speak = e.target.closest('[data-speak]');

  if (speak) {
    const pre = speak.closest('.bubble').querySelector('pre.draft');
    const text = pre ? (pre.dataset.text || pre.textContent) : '';
    if (text && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
      speak.textContent = 'Reading…';
      setTimeout(() => (speak.textContent = 'Read aloud'), 2500);
    } else {
      speak.textContent = 'No voice';
    }
  }

  if (copy) {
    const pre = copy.closest('.bubble').querySelector('pre.draft');
    if (pre) {
      try {
        await navigator.clipboard.writeText(pre.dataset.text || pre.textContent);
        copy.textContent = 'Copied';
        setTimeout(() => (copy.textContent = 'Copy'), 1500);
      } catch {
        copy.textContent = 'Press Ctrl+C';
      }
    }
  }

  if (wa) {
    const pre = wa.closest('.bubble').querySelector('pre.draft');
    if (pre) {
      const text = encodeURIComponent(pre.dataset.text || pre.textContent);
      window.open('https://wa.me/?text=' + text, '_blank', 'noopener');
    }
  }

  if (lang) {
    const cid = (lang.closest('.bubble').querySelector('pre.draft')?.dataset.text || '').match(/\(C\d{3}\)/);
    const who = cid ? cid[1] : '';
    send(`Draft a reminder for ${who} in ${lang.dataset.lang === 'hi' ? 'Hindi' : 'English'}`);
  }

  if (prom) {
    e.preventDefault();
    openPromise(prom.dataset.promise);
  }

  if (cont) {
    e.preventDefault();
    openContact(cont.dataset.contact);
  }
});

// ---------- promise dialog ----------
function openPromise(cid) {
  promiseFor = cid;
  document.getElementById('promisecid').textContent = cid;
  const existing = promises[cid];
  document.getElementById('promisedate').value = existing?.promised_on || '';
  document.getElementById('promisenote').value = existing?.note || '';
  dlg.showModal();
}

document.getElementById('promisecancel').addEventListener('click', () => dlg.close());

document.getElementById('promiseclear').addEventListener('click', async () => {
  await savePromise(true);
});

document.getElementById('promiseform').addEventListener('submit', async (e) => {
  e.preventDefault();
  await savePromise(false);
});

async function savePromise(clear) {
  if (!promiseFor) return;
  const body = clear
    ? { customer_id: promiseFor, clear: true }
    : { customer_id: promiseFor, date: document.getElementById('promisedate').value, note: document.getElementById('promisenote').value };
  if (!clear && !body.date) return;
  await fetch('/api/promise', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  dlg.close();
  await loadRegister();
  addMsg('bot', clear
    ? `<p>Promise cleared for <strong>${promiseFor}</strong>.</p>`
    : `<p>Promise recorded for <strong>${promiseFor}</strong> — ${body.date}. It now leads the follow-up list.</p>`);
  setChips(['What is due for follow-up?', 'Top 3 customers to chase']);
}

// ---------- contact dialog ----------
function openContact(cid) {
  contactFor = cid;
  document.getElementById('contactcid').textContent = cid;
  const existing = contacts[cid];
  document.getElementById('contactoutcome').value = existing?.outcome || 'no answer';
  document.getElementById('contactnote').value = existing?.note || '';
  document.getElementById('contactclear').hidden = !existing;
  contactDlg.showModal();
}

document.getElementById('contactcancel').addEventListener('click', () => contactDlg.close());

document.getElementById('contactclear').addEventListener('click', async () => {
  if (!contactFor) return;
  await fetch('/api/contact', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ customer_id: contactFor, clear: true }),
  });
  contactDlg.close();
  await loadRegister();
  addMsg('bot', `<p>Contact record cleared for <strong>${contactFor}</strong>.</p>`);
});

document.getElementById('contactform').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!contactFor) return;
  const outcome = document.getElementById('contactoutcome').value;
  await fetch('/api/contact', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      customer_id: contactFor,
      outcome,
      note: document.getElementById('contactnote').value,
    }),
  });
  contactDlg.close();
  await loadRegister();
  addMsg('bot', outcome === 'disputed'
    ? `<p><strong>${contactFor}</strong> marked under dispute. It stays scored, but it is flagged in the list and can be found with <em>“show disputed invoices”</em>.</p>`
    : `<p>Contact logged for <strong>${contactFor}</strong> — ${outcome}. It drops out of <em>“not contacted in 7 days”</em>.</p>`);
  setChips(['Show disputed invoices', 'Not contacted in 7 days', 'What is due for follow-up?']);
});

// ---------- version switch ----------
function applyMode(next) {
  mode = next;
  document.getElementById('mode-v1').classList.toggle('on', next === 'v1');
  document.getElementById('mode-v2').classList.toggle('on', next === 'v2');
}

function setMode(next) {
  applyMode(next);
  addMsg('bot', next === 'v1'
    ? '<p><strong>Version 1 active.</strong> Days overdue are counted from the dates by the assistant. Boundary rows can be wrong — compare against Version 2.</p>'
    : '<p><strong>Version 2 active.</strong> Days overdue come from the register column, so boundary rows are exact.</p>');
  setChips(['Top 3 customers to chase', 'Score C002', 'Score C003']);
}

document.getElementById('mode-v1').addEventListener('click', () => setMode('v1'));
document.getElementById('mode-v2').addEventListener('click', () => setMode('v2'));

// ---------- exposure strip ----------
function renderExposure(summary) {
  const order = ['Critical', 'High', 'Medium', 'Low'];
  const total = summary.total_amount || 0;
  exposure.innerHTML =
    '<span class="explabel">Open exposure</span>' +
    '<strong class="exptotal">' + money(total) + '</strong>' +
    order
      .map((p) => {
        const b = summary.bands[p];
        const share = total ? Math.round((b.amount / total) * 100) : 0;
        return `<button class="expband ${p.toLowerCase()}" data-pack="${p}" title="Generate the ${p} reminder pack">
            <span class="expname">${p}</span>
            <span class="expcount">${b.count} inv</span>
            <span class="expamt">${money(b.amount)}</span>
            <span class="expshare">${share}%</span>
          </button>`;
      })
      .join('') +
    (summary.partial_rows
      ? `<span class="exppartial">${summary.partial_rows} provisional row(s) — missing data</span>`
      : '');
}

function money(n) {
  return 'Rs ' + (n || 0).toLocaleString('en-IN');
}

// ---------- register table ----------
function renderRows() {
  const q = filter.value.trim().toUpperCase();
  regBody.innerHTML = '';
  rows
    .filter((r) => {
      if (activePriority === 'Followup') return !!r.promised_on;
      if (activePriority === 'Disputed') return r.outcome === 'disputed';
      return activePriority === 'All' || r.priority === activePriority;
    })
    .filter((r) => !q || r.customer_id.includes(q) || r.priority.toUpperCase().includes(q))
    .forEach((r) => {
      const tr = document.createElement('tr');
      const promised = r.promised_on
        ? ` <span class="promiseflag" title="Promised ${r.promised_on}">P</span>`
        : '';
      const disputed = r.outcome === 'disputed'
        ? ' <span class="disputeflag" title="Under dispute">D</span>'
        : '';
      tr.innerHTML =
        '<td>' + r.customer_id + (r.partial ? ' <span class="flag">!</span>' : '') + promised + disputed + '</td>' +
        '<td class="num">' + (r.days === null ? '—' : r.days) + '</td>' +
        '<td class="num">' + (r.amount_text || '—') + '</td>' +
        '<td class="num">' + r.score + '</td>' +
        '<td><span class="pill ' + r.priority.toLowerCase() + '">' + r.priority + '</span></td>';
      tr.addEventListener('click', () => send('Score ' + r.customer_id));
      regBody.appendChild(tr);
    });
}

filter.addEventListener('input', renderRows);

pfilters.addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-p]');
  if (!btn) return;
  activePriority = btn.dataset.p;
  [...pfilters.querySelectorAll('button')].forEach((b) => b.classList.toggle('on', b === btn));
  renderRows();
});

// ---------- reminder packs ----------
document.addEventListener('click', (e) => {
  const pack = e.target.closest('[data-pack]');
  if (pack) {
    const chosen = pack.dataset.pack;
    const p = chosen === 'auto'
      ? (['Critical', 'High', 'Medium', 'Low'].includes(activePriority) ? activePriority : 'Critical')
      : chosen;
    const lang = /hindi|हिंदी/i.test(input.value) ? 'hi' : 'en';
    window.location.href = `/api/pack?priority=${encodeURIComponent(p)}&lang=${lang}`;
  }
});

// ---------- dataset import ----------
const importDlg = document.getElementById('importdlg');
const importFile = document.getElementById('importfile');
const importDate = document.getElementById('importdate');
const importMap = document.getElementById('importmap');
const importIssues = document.getElementById('importissues');
const importSample = document.getElementById('importsample');
const importApply = document.getElementById('importapply');
let importText = '';
let importInfo = null;

async function importStatus() {
  const data = await (await fetch('/api/dataset')).json();
  document.getElementById('health').textContent =
    data.customers + ' customers · as on ' + data.report_date;
  if (!importDate.value) importDate.value = data.report_date;
  paintDataset(data);
  return data;
}

function paintDataset(data) {
  const imported = data.source !== 'shipped register';
  document.getElementById('dataset-badge').hidden = !imported;
  const banner = document.getElementById('dsbanner');
  banner.hidden = !imported;
  if (imported) {
    banner.textContent =
      'Imported dataset, scored as on ' + data.report_date + '. The Policy is still the ABC Traders '
      + 'policy — check its bands and actions suit this book before relying on a band. '
      + 'Restore the demo register from Import a dataset…';
  }
  const when = new Date(data.report_date + 'T00:00:00');
  document.getElementById('asof').innerHTML = 'as on <strong>' + when.toDateString() + '</strong>';
}

document.getElementById('import-open').addEventListener('click', async () => {
  importText = '';
  importInfo = null;
  importFile.value = '';
  importMap.innerHTML = '';
  importIssues.innerHTML = '';
  importSample.innerHTML = '';
  importApply.disabled = true;
  await importStatus();
  importDlg.showModal();
});

document.getElementById('importcancel').addEventListener('click', () => importDlg.close());

importFile.addEventListener('change', async () => {
  const file = importFile.files[0];
  if (!file) return;
  importText = await file.text();
  await runPreview();
});

importDate.addEventListener('change', () => { if (importText) runPreview(); });

function mappingSelects(info, headers) {
  importMap.innerHTML = '<h4>Columns</h4>';
  Object.entries(info.labels).forEach(([field, label]) => {
    const required = info.required.includes(field);
    const row = document.createElement('label');
    row.className = 'maprow' + (required ? ' req' : '');
    row.textContent = label + (required ? ' *' : '');
    const select = document.createElement('select');
    select.dataset.field = field;
    select.innerHTML = '<option value="">— none —</option>';
    headers.forEach((h) => {
      const opt = document.createElement('option');
      opt.value = h;
      opt.textContent = h;
      if (info.mapping[field] === h) opt.selected = true;
      select.appendChild(opt);
    });
    select.addEventListener('change', runPreview);
    row.appendChild(select);
    importMap.appendChild(row);
  });
}

async function runPreview() {
  if (!importText) return;
  const mapping = {};
  importMap.querySelectorAll('select[data-field]').forEach((s) => {
    if (s.value) mapping[s.dataset.field] = s.value;
  });
  const res = await fetch('/api/dataset/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ csv: importText, mapping, report_date: importDate.value }),
  });
  const info = await res.json();
  if (!res.ok) {
    importIssues.innerHTML = `<p class="warn">${info.error || 'Could not read the file'}</p>`;
    importApply.disabled = true;
    return;
  }
  importInfo = info;
  mappingSelects(info, info.headers);

  importIssues.innerHTML = '';
  info.issues.forEach((text) => {
    const p = document.createElement('p');
    p.className = 'note';
    p.textContent = text;
    importIssues.appendChild(p);
  });
  if (info.missing.length) {
    const p = document.createElement('p');
    p.className = 'warn';
    p.textContent = 'Map these columns to continue: ' + info.missing.join(', ');
    importIssues.appendChild(p);
  }

  importSample.innerHTML = info.preview_days && info.preview_days.length
    ? '<h4>First rows, scored at that date</h4><table class="tbl"><thead><tr><th>Customer</th><th>Due</th><th>Days</th><th>Amount</th><th>Priority</th></tr></thead><tbody>'
      + info.preview_days.map((r) =>
        `<tr><td>${r.customer_id}</td><td>${r.due_date || '—'}</td><td>${r.days ?? '—'}</td>`
        + `<td>${r.amount === null ? '—' : money(r.amount)}</td>`
        + `<td><span class="pill ${r.priority.toLowerCase()}">${r.priority}</span></td></tr>`).join('')
      + '</tbody></table>'
    : '';

  importApply.disabled = !info.ok;
  importApply.textContent = info.ok ? `Import ${info.customers} customers` : 'Import';
}

document.getElementById('importform').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!importText || !importInfo) return;
  const mapping = {};
  importMap.querySelectorAll('select[data-field]').forEach((s) => {
    if (s.value) mapping[s.dataset.field] = s.value;
  });
  const res = await fetch('/api/dataset/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ csv: importText, mapping, report_date: importDate.value }),
  });
  const data = await res.json();
  importDlg.close();
  if (!res.ok) {
    addMsg('bot', `<p class="warn">Import rejected: ${data.error || 'unknown error'}</p>`);
    return;
  }
  applyMode('v1');
  await loadRegister();
  addMsg('bot',
    `<p><strong>${data.customers} customers imported</strong>, scored as on ${data.report_date}. ` +
    'The switch is on Version 1 so the dates are counted by the bot and you can see whether the ' +
    'due dates were read correctly — compare a row, then switch to Version 2.</p>');
  setChips(['Give me all the overdue list', 'Ageing report', 'Total overdue for this month only']);
});

document.getElementById('importreset').addEventListener('click', async () => {
  const res = await fetch('/api/dataset/reset', { method: 'POST' });
  const data = await res.json();
  importDlg.close();
  engineFreeReload(data);
});

async function engineFreeReload(data) {
  applyMode('v2');
  await loadRegister();
  addMsg('bot', `<p>Demo register restored — <strong>${data.customers}</strong> invoices, as on ${data.report_date}.</p>`);
  setChips(OPENING);
}

async function loadRegister() {
  const res = await fetch('/api/register');
  const data = await res.json();
  rows = data.rows;
  promises = {};
  rows.forEach((r) => {
    if (r.promised_on) promises[r.customer_id] = { promised_on: r.promised_on };
  });
  try {
    contacts = (await (await fetch('/api/contacts')).json()).contacts || {};
  } catch { contacts = {}; }
  rows.forEach((r) => {
    if (contacts[r.customer_id]) r.outcome = contacts[r.customer_id].outcome;
  });
  renderRows();
  await importStatus();
  const sum = await (await fetch('/api/summary')).json();
  renderExposure(sum);
  try {
    const status = await (await fetch('/api/status')).json();
    const badge = document.getElementById('ai-status');
    badge.textContent = status.ai ? 'Gemini reading questions' : 'rules only';
    badge.className = status.ai ? 'ai-badge on' : 'ai-badge';
    badge.title = status.ai
      ? 'Gemini only turns your sentence into a query; all arithmetic stays in the rule engine.'
      : 'No GEMINI_API_KEY set — the built-in parser handles every question.';
  } catch { /* status is cosmetic */ }
}

async function boot() {
  setChips(OPENING);
  addMsg('bot',
    '<p>Good day. I am the <strong>ABC Traders receivables assistant</strong>. I score overdue invoices against the Collections Policy and draft the reminder.</p>' +
    '<p>Ask for a ranking, a single Customer ID, or a reminder draft. Every figure cites Policy or Register.</p>');
  setChips(OPENING);
  try {
    await loadRegister();
  } catch {
    document.getElementById('health').textContent = 'register unavailable';
  }
  const preset = new URLSearchParams(location.search);
  const pm = preset.get('mode');
  if (pm === 'v1' || pm === 'v2') applyMode(pm);
  const q = preset.get('q');
  if (q) send(q);
  if (preset.get('import')) document.getElementById('import-open').click();
}

boot();
