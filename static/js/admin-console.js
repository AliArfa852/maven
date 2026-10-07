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
  el('ac-compliance').hidden = !caps.includes('compliance.review');

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
