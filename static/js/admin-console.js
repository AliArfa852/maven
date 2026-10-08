// Admin console: what is shown follows the viewer's capabilities
// (src/access.py). The server enforces every read and change; hiding a
// control here is only presentation.

const el = (id) => document.getElementById(id);

const CAPABILITY_TEXT = {
  'admin.manage': 'change everything',
  'admin.view': 'view',
  'compliance.review': 'review flags',
};

// "general_manager" -> "General Manager", for the header before the
// role catalogue (admin.view only) has loaded.
function roleLabel(id) {
  return String(id).split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

function node(tag, text, className) {
  const n = document.createElement(tag);
  if (text != null) n.textContent = text;
  if (className) n.className = className;
  return n;
}

async function api(path, options = {}) {
  const res = await fetch(path, { credentials: 'same-origin', ...options });
  let body = null;
  try { body = await res.json(); } catch { /* empty body */ }
  if (!res.ok) throw new Error((body && body.detail) || `Request failed (${res.status})`);
  return body;
}

function consoleAccess(caps) {
  return ['admin.manage', 'admin.view', 'compliance.review']
    .filter((c) => caps.includes(c))
    .map((c) => CAPABILITY_TEXT[c]);
}

function renderRoles(catalogue) {
  const rows = el('ac-role-rows');
  rows.replaceChildren();
  for (const role of catalogue.roles) {
    const tr = node('tr');
    tr.append(node('td', role.label), node('td', role.default_clearance));
    const access = consoleAccess(role.capabilities);
    tr.append(node('td', access.length ? access.join(', ') : 'none'));
    rows.append(tr);
  }
}

function renderUsers(users, catalogue, canManage, me) {
  const rows = el('ac-user-rows');
  rows.replaceChildren();
  const labels = Object.fromEntries(catalogue.roles.map((r) => [r.id, r.label]));
  for (const user of users) {
    const tr = node('tr');
    const name = node('td', user.username);
    if (user.username === me) name.append(node('span', ' (you)', 'sub'));
    tr.append(name);

    const rolesCell = node('td');
    const clearanceCell = node('td');
    const actionCell = node('td');
    if (canManage) {
      const boxes = [];
      for (const role of catalogue.roles) {
        const label = node('label', null, 'role');
        const box = document.createElement('input');
        box.type = 'checkbox';
        box.value = role.id;
        box.checked = user.roles.includes(role.id);
        // Everyone holds Basic; it cannot be removed.
        if (role.id === 'basic') { box.checked = true; box.disabled = true; }
        boxes.push(box);
        label.append(box, document.createTextNode(role.label));
        rolesCell.append(label);
      }

      const select = document.createElement('select');
      const def = document.createElement('option');
      def.value = '';
      def.textContent = `Role default (${user.clearance_default})`;
      select.append(def);
      for (const level of catalogue.clearances) {
        const opt = document.createElement('option');
        opt.value = level;
        opt.textContent = level;
        select.append(opt);
      }
      select.value = user.clearance_override || '';
      clearanceCell.append(select);

      const save = node('button', 'Save');
      save.addEventListener('click', () => saveUser(user.username, boxes, select, save));
      actionCell.append(save);
    } else {
      for (const r of user.roles) rolesCell.append(node('span', labels[r] || r, 'badge'));
      clearanceCell.textContent = user.clearance + (user.clearance_override ? ' (set by admin)' : '');
    }
    tr.append(rolesCell, clearanceCell, actionCell);
    rows.append(tr);
  }
}

async function saveUser(username, boxes, select, button) {
  const status = el('ac-users-status');
  button.disabled = true;
  status.className = 'status';
  status.textContent = `Saving ${username}…`;
  try {
    const roles = boxes.filter((b) => b.checked).map((b) => b.value);
    const enc = encodeURIComponent(username);
    const json = { 'Content-Type': 'application/json' };
    const r = await api(`/api/auth/users/${enc}/roles`, {
      method: 'PUT', headers: json, body: JSON.stringify({ roles }),
    });
    await api(`/api/auth/users/${enc}/clearance`, {
      method: 'PUT', headers: json, body: JSON.stringify({ clearance: select.value || null }),
    });
    // Removing your own Admin role changes what this page may show.
    if (r.self) { window.location.reload(); return; }
    status.textContent = `Saved ${username}.`;
    await load();
  } catch (err) {
    status.className = 'status error';
    status.textContent = `${username}: ${err.message}`;
  } finally {
    button.disabled = false;
  }
}

// ── Flagged conversations (compliance.review only) ──

async function loadFlags() {
  const status = el('ac-flag-status').value;
  const box = el('ac-flags-status');
  box.className = 'status';
  box.textContent = 'Loading…';
  try {
    const data = await api(`/api/compliance/flags?status=${encodeURIComponent(status)}`);
    const c = data.counts || {};
    el('ac-flag-counts').textContent =
      `${c.open || 0} open · ${c.escalated || 0} escalated · ${c.warned || 0} warned · ${c.dismissed || 0} dismissed` +
      (data.retention_days ? ` · decided flags are deleted after ${data.retention_days} days` : ' · decided flags are kept');
    renderFlags(data.flags || []);
    box.textContent = data.flags && data.flags.length ? '' : 'Nothing here.';
  } catch (err) {
    box.className = 'status error';
    box.textContent = err.message;
  }
}

function renderFlags(flags) {
  const rows = el('ac-flag-rows');
  rows.replaceChildren();
  for (const f of flags) {
    const tr = node('tr');
    tr.append(node('td', f.created_at ? new Date(f.created_at).toLocaleString() : ''));
    tr.append(node('td', f.owner || 'unknown'));
    const why = node('td');
    why.append(node('span', f.category_label, f.severity === 'high' ? 'sev-high' : ''));
    why.append(node('div', `${f.rule} · ${f.severity}`, 'sub'));
    tr.append(why);
    tr.append(node('td', f.excerpt, 'excerpt'));
    const act = node('td', null, 'actions');
    if (f.status === 'open') {
      for (const [decision, label] of [['dismiss', 'Dismiss'], ['warn', 'Warn'], ['escalate', 'Escalate']]) {
        const b = node('button', label);
        b.addEventListener('click', () => decideFlag(f.id, decision, b));
        act.append(b);
      }
    } else {
      act.append(node('div', `${f.status} by ${f.reviewed_by || '?'}`));
      if (f.review_note) act.append(node('div', f.review_note, 'sub'));
    }
    tr.append(act);
    rows.append(tr);
  }
}

async function decideFlag(id, decision, button) {
  const note = window.prompt(`Optional note for "${decision}":`, '');
  if (note === null) return; // cancelled
  button.disabled = true;
  try {
    await api(`/api/compliance/flags/${encodeURIComponent(id)}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, note }),
    });
    await loadFlags();
  } catch (err) {
    el('ac-flags-status').className = 'status error';
    el('ac-flags-status').textContent = err.message;
    button.disabled = false;
  }
}

// ── Flagging rules (compliance.review only) ──

function renderSettings(data) {
  el('ac-flagging-off').hidden = data.flagging_enabled;
  el('ac-keywords').value = (data.keywords || []).join('\n');
  const envNote = el('ac-env-keywords');
  envNote.hidden = !(data.env_keywords || []).length;
  envNote.textContent = `Also set by the server (MAVEN_AI_FLAG_KEYWORDS, not editable here): ${(data.env_keywords || []).join(', ')}`;
  const off = new Set(data.disabled_rules || []);
  const rows = el('ac-rule-rows');
  rows.replaceChildren();
  for (const r of data.rules || []) {
    const tr = node('tr');
    const cell = node('td');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.value = r.rule;
    box.checked = !off.has(r.rule);
    box.setAttribute('aria-label', `Rule ${r.rule} on`);
    cell.append(box);
    tr.append(cell, node('td', r.rule), node('td', r.category_label),
      node('td', r.severity, r.severity === 'high' ? 'sev-high' : ''));
    rows.append(tr);
  }
  el('ac-settings-status').textContent = data.updated_at
    ? `Last changed by ${data.updated_by || '?'} at ${new Date(data.updated_at).toLocaleString()}`
    : '';
}

async function loadSettings() {
  renderSettings(await api('/api/compliance/settings'));
  el('ac-flag-settings').hidden = false;
}

async function saveSettings() {
  const button = el('ac-settings-save');
  const status = el('ac-settings-status');
  button.disabled = true;
  status.className = 'status';
  status.textContent = 'Saving…';
  try {
    const keywords = el('ac-keywords').value.split('\n').map((k) => k.trim()).filter(Boolean);
    const disabled_rules = [...el('ac-rule-rows').querySelectorAll('input[type=checkbox]')]
      .filter((b) => !b.checked).map((b) => b.value);
    const data = await api('/api/compliance/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keywords, disabled_rules }),
    });
    renderSettings(data);
    status.textContent = `Saved. ${status.textContent}`;
  } catch (err) {
    status.className = 'status error';
    status.textContent = err.message;
  } finally {
    button.disabled = false;
  }
}

// ── Audit log (admin.view or compliance.review) ──

const AUDIT_LABELS = {
  'auth.login': 'Sign-in',
  'access.roles': 'Roles changed',
  'access.clearance': 'Clearance changed',
};
let auditBefore = null;

function auditWhat(e) {
  if (AUDIT_LABELS[e.action]) return AUDIT_LABELS[e.action];
  if (e.action.startsWith('http.')) return `${e.action.slice(5)} request`;
  return e.action;
}

function auditDetail(e) {
  const d = e.detail || {};
  if (e.action === 'access.roles' && d.after) return `${(d.before || []).join(', ') || 'none'} → ${d.after.join(', ')}`;
  if (e.action === 'access.clearance') return d.override ? `set to ${d.override}` : 'reset to role default';
  if (d.reason) return d.reason;
  return '';
}

async function loadAudit(more = false) {
  const status = el('ac-audit-status');
  status.className = 'status';
  status.textContent = 'Loading…';
  const params = new URLSearchParams({ limit: '100' });
  if (el('ac-audit-filter').value) params.set('action', el('ac-audit-filter').value);
  if (el('ac-audit-outcome').value) params.set('outcome', el('ac-audit-outcome').value);
  if (more && auditBefore) params.set('before_id', String(auditBefore));
  try {
    const data = await api(`/api/audit/events?${params}`);
    const rows = el('ac-audit-rows');
    if (!more) rows.replaceChildren();
    for (const e of data.events || []) {
      const tr = node('tr');
      tr.append(node('td', e.at ? new Date(e.at).toLocaleString() : ''), node('td', e.actor || '—'));
      const what = node('td', auditWhat(e));
      const extra = auditDetail(e);
      if (extra) what.append(node('div', extra, 'sub'));
      tr.append(what, node('td', e.target || '', 'excerpt'),
        node('td', e.outcome, e.outcome === 'ok' ? '' : 'sev-high'), node('td', e.ip || ''));
      rows.append(tr);
    }
    auditBefore = data.next_before_id;
    el('ac-audit-more').hidden = !auditBefore;
    status.textContent = rows.children.length ? '' : 'Nothing recorded yet.';
  } catch (err) {
    status.className = 'status error';
    status.textContent = err.message;
  }
}

async function verifyAudit() {
  const out = el('ac-audit-chain');
  out.className = 'sub';
  out.textContent = 'Checking…';
  try {
    const r = await api('/api/audit/verify');
    if (r.ok) {
      out.textContent = `Intact: ${r.count} entries. Latest hash ${r.head ? r.head.slice(0, 16) + '…' : 'none'}`;
      out.title = r.head || '';
    } else {
      out.className = 'sub error';
      out.textContent = `Broken at entry ${r.first_bad_id}: ${r.reason}`;
    }
  } catch (err) {
    out.className = 'sub error';
    out.textContent = err.message;
  }
}

async function load() {
  const brand = window.MAVEN_BRAND ? window.MAVEN_BRAND.name : '';
  el('ac-title').textContent = brand ? `${brand} Admin Console` : 'Admin Console';
  document.title = el('ac-title').textContent;

  const me = await api('/api/auth/status');
  const caps = me.capabilities || [];
  const roles = me.roles || [];
  const shown = roles.filter((r) => r !== 'basic' || roles.length === 1).map(roleLabel);
  el('ac-who').textContent = `${me.username || ''} · ${shown.join(', ')} · clearance ${me.clearance || ''}`;

  if (!caps.includes('admin.view')) {
    el('ac-denied').hidden = false;
    return;
  }
  const canManage = caps.includes('admin.manage');
  el('ac-viewonly').hidden = canManage;
  if (!canManage && caps.includes('compliance.review')) {
    el('ac-viewonly').textContent =
      'Users and roles are view only (an Admin changes them). You can review flagged conversations below.';
  }
  el('ac-compliance').hidden = !caps.includes('compliance.review');
  if (caps.includes('compliance.review')) {
    el('ac-flag-status').addEventListener('change', loadFlags);
    el('ac-settings-save').addEventListener('click', saveSettings);
    loadFlags();
    loadSettings().catch((err) => {
      el('ac-flags-status').className = 'status error';
      el('ac-flags-status').textContent = `Flagging rules: ${err.message}`;
    });
  }

  el('ac-audit').hidden = false;
  el('ac-audit-filter').addEventListener('change', () => loadAudit());
  el('ac-audit-outcome').addEventListener('change', () => loadAudit());
  el('ac-audit-more').addEventListener('click', () => loadAudit(true));
  el('ac-audit-verify').addEventListener('click', verifyAudit);
  loadAudit();

  const [catalogue, users] = await Promise.all([api('/api/auth/roles'), api('/api/auth/users')]);
  renderRoles(catalogue);
  renderUsers(users.users, catalogue, canManage, me.username);
  el('ac-roles').hidden = false;
  el('ac-users').hidden = false;
}

load().catch((err) => {
  const denied = el('ac-denied');
  denied.textContent = `Could not load the console: ${err.message}`;
  denied.hidden = false;
});
