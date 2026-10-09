// Admin console: what is shown follows the viewer's capabilities
// (src/access.py). The server enforces every read and change; hiding a
// control here is only presentation.

import { api, el, node } from './admin-console-util.js';
import { initModels } from './admin-console-models.js';
import { initSettings } from './admin-console-settings.js';

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
        box.dataset.initial = box.checked ? '1' : '0';
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
      select.dataset.initial = select.value;
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
    // Send only what changed, so the audit log records real changes.
    const before = select.dataset.initial || '';
    const rolesChanged = boxes.some((b) => b.checked !== (b.dataset.initial === '1'));
    let r = {};
    if (rolesChanged) {
      r = await api(`/api/auth/users/${enc}/roles`, {
        method: 'PUT', headers: json, body: JSON.stringify({ roles }),
      });
    }
    if ((select.value || '') !== before) {
      await api(`/api/auth/users/${enc}/clearance`, {
        method: 'PUT', headers: json, body: JSON.stringify({ clearance: select.value || null }),
      });
    }
    if (!rolesChanged && (select.value || '') === before) {
      status.textContent = `No changes for ${username}.`;
      return;
    }
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

// ── Tabs ──

const TABS = [
  { id: 'overview', label: 'Overview', can: () => true },
  { id: 'users', label: 'Users & roles', can: (c) => c.includes('admin.view') },
  { id: 'models', label: 'Models & APIs', can: (c) => c.includes('admin.manage') },
  { id: 'settings', label: 'Settings', can: (c) => c.includes('admin.manage') },
  { id: 'compliance', label: 'Compliance', can: (c) => c.includes('compliance.review') },
  { id: 'audit', label: 'Audit log', can: (c) => c.includes('admin.view') || c.includes('compliance.review') },
];
let allowedTabs = [];

function showTab(id) {
  if (!allowedTabs.some((t) => t.id === id)) id = 'overview';
  for (const section of document.querySelectorAll('section[data-tab]')) {
    section.hidden = section.dataset.tab !== id;
  }
  for (const b of el('ac-tabs').querySelectorAll('button')) {
    b.setAttribute('aria-selected', String(b.dataset.tab === id));
  }
  try { history.replaceState(null, '', `#${id}`); } catch { /* file:// or sandbox */ }
}

function buildTabs(caps) {
  allowedTabs = TABS.filter((t) => t.can(caps));
  const nav = el('ac-tabs');
  nav.replaceChildren();
  for (const t of allowedTabs) {
    const b = node('button', t.label);
    b.type = 'button';
    b.dataset.tab = t.id;
    b.setAttribute('role', 'tab');
    b.addEventListener('click', () => showTab(t.id));
    nav.append(b);
  }
  nav.hidden = false;
  showTab((location.hash || '').slice(1) || 'overview');
}

function tabBadge(id, n) {
  const b = el('ac-tabs').querySelector(`button[data-tab="${id}"]`);
  if (!b) return;
  b.querySelector('.count')?.remove();
  if (n) b.append(node('span', String(n), 'count'));
}

// ── Overview ──

function card(title, big, sub, tab) {
  const c = node('div', null, 'card');
  c.append(node('div', title, 'sub'), node('div', big, 'big'));
  if (sub) c.append(node('p', sub, 'sub'));
  if (tab && allowedTabs.some((t) => t.id === tab)) {
    const a = node('a', 'Open');
    a.href = `#${tab}`;
    a.addEventListener('click', (e) => { e.preventDefault(); showTab(tab); });
    c.append(a);
  }
  return c;
}

async function renderOverview(caps, me, users, endpoints) {
  const cards = el('ac-cards');
  cards.replaceChildren();
  const next = [];
  if (users) {
    const admins = users.filter((u) => u.roles.includes('admin')).length;
    cards.append(card('People', String(users.length), `${admins} admin${admins === 1 ? '' : 's'}`, 'users'));
  }
  if (endpoints) {
    const on = endpoints.filter((e) => e.is_enabled !== false);
    const online = on.filter((e) => e.status === 'online').length;
    const models = on.reduce((n, e) => n + (e.model_count ?? (e.models || []).length), 0);
    cards.append(card('Model connections', String(on.length),
      on.length ? `${online} online · ${models} models` : 'none yet', 'models'));
    if (!on.length) next.push(['Connect a model so people can chat: Ollama, LM Studio or a cloud API.', 'models']);
    else if (!online) next.push(['No model connection is online. Check that your model server is running.', 'models']);
  }
  if (caps.includes('compliance.review')) {
    try {
      const f = await api('/api/compliance/flags?status=open&limit=1');
      const open = (f.counts || {}).open || 0;
      cards.append(card('Open flags', String(open), open ? 'waiting for review' : 'nothing to review', 'compliance'));
      tabBadge('compliance', open);
    } catch { /* tab shows the error */ }
  }
  if (caps.includes('admin.view') || caps.includes('compliance.review')) {
    try {
      const v = await api('/api/audit/verify');
      cards.append(card('Audit log', v.ok ? 'Intact' : 'Broken',
        v.ok ? `${v.count} entries` : `first bad entry #${v.first_bad_id}`, 'audit'));
      if (!v.ok) next.push(['The audit log failed its integrity check. Investigate before relying on it.', 'audit']);
    } catch { /* ignore */ }
  }
  if (caps.includes('admin.manage') && me && !me.totp_enabled) {
    try {
      const t = await api('/api/auth/2fa/status');
      if (!t.enabled) next.push(['Turn on two-factor sign-in for your admin account (app Settings → Account).', null]);
    } catch { /* ignore */ }
  }
  const list = el('ac-next-list');
  list.replaceChildren();
  for (const [text, tab] of next) {
    const li = node('li', text);
    if (tab) {
      const a = node('a', ' Open');
      a.href = `#${tab}`;
      a.addEventListener('click', (e) => { e.preventDefault(); showTab(tab); });
      li.append(a);
    }
    list.append(li);
  }
  el('ac-next').hidden = !next.length;
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
      'Users and roles are view only (an Admin changes them). You can review flagged conversations.';
  }
  buildTabs(caps);

  if (caps.includes('compliance.review')) {
    el('ac-flag-status').addEventListener('change', loadFlags);
    el('ac-settings-save').addEventListener('click', saveSettings);
    loadFlags();
    loadSettings().catch((err) => {
      el('ac-flags-status').className = 'status error';
      el('ac-flags-status').textContent = `Flagging rules: ${err.message}`;
    });
  }

  el('ac-audit-filter').addEventListener('change', () => loadAudit());
  el('ac-audit-outcome').addEventListener('change', () => loadAudit());
  el('ac-audit-more').addEventListener('click', () => loadAudit(true));
  el('ac-audit-verify').addEventListener('click', verifyAudit);
  loadAudit();

  let endpoints = null;
  if (canManage) {
    endpoints = await initModels().catch(() => null);
    initSettings(me).catch((err) => {
      el('ac-set-status').className = 'status error';
      el('ac-set-status').textContent = err.message;
    });
  }

  const [catalogue, users] = await Promise.all([api('/api/auth/roles'), api('/api/auth/users')]);
  renderRoles(catalogue);
  renderUsers(users.users, catalogue, canManage, me.username);
  renderOverview(caps, me, users.users, endpoints);
}

load().catch((err) => {
  const denied = el('ac-denied');
  denied.textContent = `Could not load the console: ${err.message}`;
  denied.hidden = false;
});
