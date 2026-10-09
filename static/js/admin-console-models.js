// Admin Console: Models and APIs (Admin only). Uses the existing
// /api/model-endpoints routes, which the server restricts to Admins.

import { api, el, jsonHeaders, node, setStatus } from './admin-console-util.js';
import { invalidateSettings } from './appConfig.js';

// Local model servers. "localhost" is fine even when Maven runs in Docker:
// the server rewrites it to the host machine (host.docker.internal).
const LOCAL_PRESETS = [
  { id: 'ollama', label: 'Ollama', url: 'http://localhost:11434/v1', name: 'Ollama',
    hint: 'Ollama listens on port 11434. If Maven runs in Docker, start Ollama with OLLAMA_HOST=0.0.0.0:11434 so the container can reach it.' },
  { id: 'lmstudio', label: 'LM Studio', url: 'http://localhost:1234/v1', name: 'LM Studio',
    hint: 'In LM Studio, open the Developer tab, start the server, and turn on "Serve on local network" if Maven runs in Docker.' },
  { id: 'llamacpp', label: 'llama.cpp server', url: 'http://localhost:8080/v1', name: 'llama.cpp',
    hint: 'llama-server defaults to port 8080; use the port you started it on.' },
  { id: 'vllm', label: 'vLLM', url: 'http://localhost:8000/v1', name: 'vLLM', hint: 'vLLM serves an OpenAI-compatible API on port 8000 by default.' },
  { id: 'custom', label: 'Other OpenAI-compatible server', url: '', name: '',
    hint: 'Any server with an OpenAI-compatible /v1 API. Use its address on your network, e.g. http://192.168.1.20:8000/v1.' },
];

// Cloud providers (same list as the app's Settings → Added Models).
// Sign-in based providers (GitHub Copilot, ChatGPT subscription) need the
// browser sign-in flow in the app's Settings panel.
const CLOUD_PRESETS = [
  ['openai', 'OpenAI', 'https://api.openai.com/v1'],
  ['anthropic', 'Anthropic', 'https://api.anthropic.com'],
  ['gemini', 'Google Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai'],
  ['openrouter', 'OpenRouter', 'https://openrouter.ai/api/v1'],
  ['mistral', 'Mistral', 'https://api.mistral.ai/v1'],
  ['deepseek', 'DeepSeek', 'https://api.deepseek.com/v1'],
  ['groq', 'Groq', 'https://api.groq.com/openai/v1'],
  ['together', 'Together AI', 'https://api.together.xyz/v1'],
  ['fireworks', 'Fireworks AI', 'https://api.fireworks.ai/inference/v1'],
  ['grok', 'xAI Grok', 'https://api.x.ai/v1'],
  ['nvidia', 'NVIDIA', 'https://integrate.api.nvidia.com/v1'],
  ['ollama-cloud', 'Ollama Cloud', 'https://ollama.com/api'],
  ['zhipu', 'Z.AI (Zhipu)', 'https://api.z.ai/api/paas/v4'],
  ['custom', 'Other (custom URL)', ''],
].map(([id, label, url]) => ({ id, label, url, name: id === 'custom' ? '' : label,
  hint: id === 'custom' ? 'Any OpenAI-compatible API. Paste its base URL and key.'
    : 'Create an API key in the provider\'s dashboard and paste it here. It is stored encrypted.' }));

let endpoints = [];
let settings = {};

function where() {
  return document.querySelector('input[name="ac-ep-where"]:checked').value;
}

function presets() {
  return where() === 'local' ? LOCAL_PRESETS : CLOUD_PRESETS;
}

function fillPresets() {
  const sel = el('ac-ep-preset');
  sel.replaceChildren(...presets().map((p) => {
    const o = node('option', p.label);
    o.value = p.id;
    return o;
  }));
  applyPreset();
}

function applyPreset() {
  const p = presets().find((x) => x.id === el('ac-ep-preset').value) || presets()[0];
  el('ac-ep-url').value = p.url;
  el('ac-ep-name').value = p.name;
  el('ac-ep-hint').textContent = p.hint;
  el('ac-ep-key-row').hidden = where() === 'local';
  if (where() === 'local') el('ac-ep-key').value = '';
  setStatus('ac-ep-test-result', '');
}

function formData(extra = {}) {
  const fd = new FormData();
  fd.append('base_url', el('ac-ep-url').value.trim());
  fd.append('api_key', el('ac-ep-key').value.trim());
  for (const [k, v] of Object.entries(extra)) fd.append(k, v);
  return fd;
}

function describeTest(r) {
  if (r.count) {
    const names = (r.models || []).slice(0, 5).join(', ');
    return [`Connected: ${r.count} model${r.count === 1 ? '' : 's'} found (${names}${r.count > 5 ? ', …' : ''}).`, 'ok'];
  }
  if (r.status === 'loading') return ['The server answered and is still loading a model. Try again in a moment.', ''];
  if (r.online) return ['The server answered but listed no models. Load or pull a model on it first.', 'error'];
  return [`Could not reach it${r.ping_error ? `: ${r.ping_error}` : ''}. Check the address and that the server is running.`, 'error'];
}

async function testConnection() {
  if (!el('ac-ep-url').value.trim()) { setStatus('ac-ep-test-result', 'Enter the address first.', 'error'); return; }
  setStatus('ac-ep-test-result', 'Testing…');
  el('ac-ep-test').disabled = true;
  try {
    const r = await api('/api/model-endpoints/test', { method: 'POST', body: formData() });
    const [text, kind] = describeTest(r);
    setStatus('ac-ep-test-result', text, kind);
  } catch (err) {
    setStatus('ac-ep-test-result', err.message, 'error');
  } finally {
    el('ac-ep-test').disabled = false;
  }
}

async function saveEndpoint() {
  const url = el('ac-ep-url').value.trim();
  if (!url) { setStatus('ac-ep-test-result', 'Enter the address first.', 'error'); return; }
  if (where() === 'cloud' && !el('ac-ep-key').value.trim()) {
    setStatus('ac-ep-test-result', 'Cloud providers need an API key.', 'error'); return;
  }
  setStatus('ac-ep-test-result', 'Saving… (Maven checks the connection first)');
  el('ac-ep-save').disabled = true;
  try {
    const ep = await api('/api/model-endpoints', {
      method: 'POST',
      body: formData({
        name: el('ac-ep-name').value.trim(),
        shared: el('ac-ep-shared').checked ? 'true' : 'false',
        endpoint_kind: where() === 'cloud' ? 'api' : 'auto',
      }),
    });
    setStatus('ac-ep-test-result', '');
    el('ac-ep-form').hidden = true;
    el('ac-ep-key').value = '';
    setStatus('ac-ep-status', `Added ${ep.name || url} with ${(ep.models || []).length} model(s).`, 'ok');
    await loadEndpoints();
  } catch (err) {
    setStatus('ac-ep-test-result', err.message, 'error');
  } finally {
    el('ac-ep-save').disabled = false;
  }
}

function statusCell(ep) {
  const text = { online: 'online', empty: 'no models', offline: 'offline' }[ep.status] || ep.status || '';
  return node('td', ep.is_enabled === false ? 'switched off' : text,
    ep.is_enabled === false ? 'sub' : (ep.status === 'online' ? 'ok' : 'sev-high'));
}

function renderEndpoints() {
  const rows = el('ac-ep-rows');
  rows.replaceChildren();
  if (!endpoints.length) {
    const tr = node('tr');
    const td = node('td', 'No models connected yet. Click "Add a model" to connect Ollama, LM Studio or a cloud API.', 'sub');
    td.colSpan = 8;
    tr.append(td);
    rows.append(tr);
    return;
  }
  for (const ep of endpoints) {
    const tr = node('tr');
    tr.append(node('td', ep.name || ''), node('td', ep.base_url || '', 'mono'),
      node('td', ep.category === 'local' ? 'Local' : (ep.category === 'cloud' || ep.category === 'api') ? 'Cloud API' : (ep.category || '')),
      statusCell(ep), node('td', String(ep.model_count ?? (ep.models || []).length)),
      node('td', ep.has_key ? `…${ep.api_key_fingerprint || 'saved'}` : '—', 'mono'));
    const on = node('td');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = ep.is_enabled !== false;
    box.setAttribute('aria-label', `${ep.name} switched on`);
    box.addEventListener('change', () => toggleEndpoint(ep, box));
    on.append(box);
    const act = node('td', null, 'actions');
    const refresh = node('button', 'Refresh models');
    refresh.addEventListener('click', () => refreshEndpoint(ep, refresh));
    const del = node('button', 'Remove', 'danger');
    del.addEventListener('click', () => deleteEndpoint(ep, del));
    act.append(refresh, del);
    tr.append(on, act);
    rows.append(tr);
  }
}

async function toggleEndpoint(ep, box) {
  box.disabled = true;
  try {
    await api(`/api/model-endpoints/${encodeURIComponent(ep.id)}`, {
      method: 'PATCH', headers: jsonHeaders, body: JSON.stringify({ is_enabled: box.checked }),
    });
    setStatus('ac-ep-status', `${ep.name} switched ${box.checked ? 'on' : 'off'}.`);
    await loadEndpoints();
  } catch (err) {
    box.checked = !box.checked;
    setStatus('ac-ep-status', err.message, 'error');
  } finally {
    box.disabled = false;
  }
}

async function refreshEndpoint(ep, button) {
  button.disabled = true;
  setStatus('ac-ep-status', `Asking ${ep.name} for its models…`);
  try {
    const r = await api(`/api/model-endpoints/${encodeURIComponent(ep.id)}/models?refresh=true`);
    const n = Array.isArray(r) ? r.length : (r.models || r.items || []).length;
    setStatus('ac-ep-status', `${ep.name}: ${n} model(s).`, 'ok');
    await loadEndpoints();
  } catch (err) {
    setStatus('ac-ep-status', `${ep.name}: ${err.message}`, 'error');
  } finally {
    button.disabled = false;
  }
}

async function deleteEndpoint(ep, button) {
  let warn = '';
  try {
    const dep = await api(`/api/model-endpoints/${encodeURIComponent(ep.id)}/dependents`);
    if ((dep.dependents || []).length) warn = `\n\nIt is used by: ${dep.dependents.join(', ')}. Those settings will be cleared.`;
  } catch { /* still allow removal */ }
  if (!window.confirm(`Remove ${ep.name}? Chats using it will need another model.${warn}`)) return;
  button.disabled = true;
  try {
    await api(`/api/model-endpoints/${encodeURIComponent(ep.id)}`, { method: 'DELETE' });
    setStatus('ac-ep-status', `Removed ${ep.name}.`);
    await loadEndpoints();
  } catch (err) {
    setStatus('ac-ep-status', err.message, 'error');
    button.disabled = false;
  }
}

async function scan() {
  const out = el('ac-ep-scan-result');
  out.hidden = false;
  out.replaceChildren(node('p', 'Looking for model servers on this computer and the hosts in LLM_HOST / LLM_HOSTS…', 'status'));
  try {
    const r = await api('/api/discover');
    const known = new Set(endpoints.map((e) => (e.base_url || '').replace(/\/+$/, '')));
    // Discovery reports the chat URL; an endpoint is saved by its base URL.
    const items = (r.items || []).filter((i) => i.url)
      .map((i) => ({ ...i, url: i.url.replace(/\/chat\/completions\/?$/, '') }));
    out.replaceChildren();
    out.append(node('p', items.length ? `Found ${items.length} server(s):` : `No model servers answered on ${(r.hosts || []).join(', ') || 'this computer'}.`, 'sub'));
    for (const it of items) {
      const row = node('div', null, 'toolbar');
      const label = `${it.provider ? it.provider + ' at ' : ''}${it.url} (${(it.models || []).length} model${(it.models || []).length === 1 ? '' : 's'})`;
      row.append(node('span', label, 'mono'));
      if (known.has(it.url.replace(/\/+$/, ''))) {
        row.append(node('span', 'already added', 'sub'));
      } else {
        const add = node('button', 'Use this');
        add.addEventListener('click', () => {
          document.querySelector('input[name="ac-ep-where"][value="local"]').checked = true;
          fillPresets();
          el('ac-ep-preset').value = 'custom';
          el('ac-ep-url').value = it.url;
          el('ac-ep-name').value = it.provider ? `${it.provider} (${it.host})` : it.host;
          el('ac-ep-form').hidden = false;
          el('ac-ep-name').focus();
        });
        row.append(add);
      }
      out.append(row);
    }
  } catch (err) {
    out.replaceChildren(node('p', err.message, 'status error'));
  }
}

// ── default models ──

function modelOptions(select, endpointId, model) {
  select.replaceChildren();
  const none = node('option', 'Not set (each user picks)');
  none.value = '';
  select.append(none);
  for (const ep of endpoints.filter((e) => e.is_enabled !== false)) {
    const group = document.createElement('optgroup');
    group.label = ep.name;
    for (const m of ep.models || []) {
      const o = node('option', m);
      o.value = `${ep.id}\u0000${m}`;
      group.append(o);
    }
    if (group.children.length) select.append(group);
  }
  select.value = endpointId && model ? `${endpointId}\u0000${model}` : '';
  if (endpointId && model && select.value === '') {
    const o = node('option', `${model} (not currently available)`);
    o.value = `${endpointId}\u0000${model}`;
    select.append(o);
    select.value = o.value;
  }
}

function renderDefaults() {
  modelOptions(el('ac-def-chat'), settings.default_endpoint_id, settings.default_model);
  modelOptions(el('ac-def-utility'), settings.utility_endpoint_id, settings.utility_model);
  el('ac-def-share').checked = !!settings.share_defaults_with_users;
}

async function saveDefaults() {
  const [ce, cm] = (el('ac-def-chat').value || '\u0000').split('\u0000');
  const [ue, um] = (el('ac-def-utility').value || '\u0000').split('\u0000');
  setStatus('ac-def-status', 'Saving…');
  try {
    settings = await api('/api/auth/settings', {
      method: 'POST', headers: jsonHeaders,
      body: JSON.stringify({ default_endpoint_id: ce, default_model: cm, utility_endpoint_id: ue,
        utility_model: um, share_defaults_with_users: el('ac-def-share').checked }),
    }) || settings;
    invalidateSettings();
    setStatus('ac-def-status', 'Saved.', 'ok');
  } catch (err) {
    setStatus('ac-def-status', err.message, 'error');
  }
}

export async function loadEndpoints() {
  try {
    endpoints = await api('/api/model-endpoints');
    renderEndpoints();
    renderDefaults();
    return endpoints;
  } catch (err) {
    setStatus('ac-ep-status', err.message, 'error');
    return [];
  }
}

export async function initModels() {
  for (const r of document.querySelectorAll('input[name="ac-ep-where"]')) r.addEventListener('change', fillPresets);
  el('ac-ep-preset').addEventListener('change', applyPreset);
  el('ac-ep-add').addEventListener('click', () => {
    el('ac-ep-form').hidden = !el('ac-ep-form').hidden;
    if (!el('ac-ep-form').hidden) { fillPresets(); el('ac-ep-url').focus(); }
  });
  el('ac-ep-cancel').addEventListener('click', () => { el('ac-ep-form').hidden = true; });
  el('ac-ep-test').addEventListener('click', testConnection);
  el('ac-ep-save').addEventListener('click', saveEndpoint);
  el('ac-ep-scan').addEventListener('click', scan);
  el('ac-ep-refresh').addEventListener('click', async () => {
    setStatus('ac-ep-status', 'Checking…');
    try { await api('/api/model-endpoints/probe-local'); } catch { /* status below still refreshes */ }
    await loadEndpoints();
    setStatus('ac-ep-status', 'Status updated.');
  });
  el('ac-def-save').addEventListener('click', saveDefaults);
  try { settings = await api('/api/auth/settings'); } catch { settings = {}; }
  return loadEndpoints();
}
