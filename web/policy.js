const GROUPS = [
  ['days overdue', 'Days overdue → points (Policy §4.1)'],
  ['amount', 'Invoice amount → points (Policy §4.2)'],
  ['history', 'Payment history → points (Policy §4.3)'],
  ['priority', 'Total score → priority band (Policy §5)'],
];

const DERIVED_TITLES = {
  'policy: days': 'Re-derived from the Policy text — days',
  'policy: amount': 'Re-derived from the Policy text — amount',
  'policy: history': 'Re-derived from the Policy text — history',
  'policy: priority': 'Re-derived from the Policy text — priority',
  'policy: layout': 'Policy layout — bands must join without gaps',
};

function table(rows) {
  const t = document.createElement('table');
  t.innerHTML =
    '<thead><tr><th>Input</th><th>Source says</th><th>Engine says</th><th>Result</th></tr></thead>';
  const body = document.createElement('tbody');
  rows.forEach((r) => {
    const tr = document.createElement('tr');
    tr.className = r.ok ? '' : 'fail';
    tr.innerHTML =
      `<td>${r.case}</td><td>${r.expected}</td><td>${r.actual}</td>` +
      `<td class="${r.ok ? 'ok' : 'no'}">${r.ok ? 'pass' : 'FAIL'}</td>`;
    body.appendChild(tr);
  });
  t.appendChild(body);
  return t;
}

fetch('/api/policy-check')
  .then((r) => r.json())
  .then((data) => {
    const derived = data.derived || [];
    const derivedFails = derived.filter((r) => !r.ok).length;
    const score = document.getElementById('score');
    const allPass = data.passed === data.total && derivedFails === 0;
    score.className = 'score ' + (allPass ? 'pass' : 'fail');
    score.textContent = allPass
      ? `All ${data.total} hand-checked cases and ${derived.length} Policy-derived cases pass`
      : `${data.total - data.passed + derivedFails} check(s) FAILED`;
    document.getElementById('boundary').textContent = data.boundary_note;

    const host = document.getElementById('tables');
    GROUPS.forEach(([key, title]) => {
      const rows = data.rows.filter((r) => r.group === key);
      if (!rows.length) return;
      const h2 = document.createElement('h2');
      h2.textContent = title;
      host.appendChild(h2);
      host.appendChild(table(rows));
    });

    // Second block: the same promises, re-derived from the Policy file itself.
    const order = Object.keys(DERIVED_TITLES).filter((k) => derived.some((r) => r.group === k));
    if (order.length) {
      const note = document.createElement('p');
      note.className = 'note';
      note.textContent =
        'These cases were not written by hand. The page reads the band tables back out of ' +
        'knowledge/Collections_Policy.md and re-derives every edge, so editing the Policy without ' +
        'following it in the engine turns this block red.';
      host.appendChild(note);
    }
    order.forEach((key) => {
      const rows = derived.filter((r) => r.group === key);
      const h2 = document.createElement('h2');
      h2.textContent = DERIVED_TITLES[key];
      host.appendChild(h2);
      host.appendChild(table(rows));
    });
  })
  .catch(() => {
    document.getElementById('score').textContent = 'Could not load the check.';
  });
