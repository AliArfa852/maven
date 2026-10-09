// Admin Console: server-wide settings (Admin only). Reads and writes the
// existing /api/auth/settings, /api/auth/features and /api/auth/open-signup
// routes. API keys are never shown: an empty key box keeps the saved key.

import { api, el, jsonHeaders, node, setStatus } from './admin-console-util.js';
import { invalidateSettings } from './appConfig.js';

const FEATURE_LABELS = {
  web_search: 'Web search',
  web_fetch: 'Reading web pages',
  deep_research: 'Deep Research',
  memory: 'Memory',
  document_editor: 'Document editor',
  rag: 'Search in personal documents',
  sensitive_filter: 'Hide sensitive content in previews',
  gallery: 'Image gallery',
};

const TEXT = ['search_provider', 'search_safesearch', 'google_pse_cx', 'app_public_url'];
const NUMBERS = ['search_result_count', 'agent_max_rounds', 'agent_max_tool_calls'];
const CHECKS = ['agent_email_confirm'];
const SECRETS = ['brave_api_key', 'tavily_api_key', 'serper_api_key', 'google_pse_key'];

let features = {};

function renderFeatures() {
  const box = el('ac-features');
  box.replaceChildren();
  for (const [key, on] of Object.entries(features)) {
    const label = node('label', null, 'check');
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = !!on;
    input.dataset.feature = key;
    label.append(input, document.createTextNode(FEATURE_LABELS[key] || key.replace(/_/g, ' ')));
    box.append(label);
  }
}

function fill(settings) {
  for (const k of TEXT) if (el(`ac-set-${k}`)) el(`ac-set-${k}`).value = settings[k] ?? '';
  for (const k of NUMBERS) if (el(`ac-set-${k}`)) el(`ac-set-${k}`).value = settings[k] ?? '';
  for (const k of CHECKS) if (el(`ac-set-${k}`)) el(`ac-set-${k}`).checked = !!settings[k];
  for (const k of SECRETS) {
    const input = el(`ac-set-${k}`);
    input.value = '';
    input.placeholder = settings[k] ? 'Saved (type to replace)' : 'Not set';
  }
}

async function save() {
  const body = {};
  for (const k of TEXT) body[k] = el(`ac-set-${k}`).value.trim();
  for (const k of NUMBERS) {
    const v = el(`ac-set-${k}`).value;
    if (v !== '') body[k] = Number(v);
  }
  for (const k of CHECKS) body[k] = el(`ac-set-${k}`).checked;
  for (const k of SECRETS) {
    const v = el(`ac-set-${k}`).value.trim();
    if (v) body[k] = v; // empty = keep the saved key
  }
  const nextFeatures = {};
  for (const input of el('ac-features').querySelectorAll('input[data-feature]')) {
    nextFeatures[input.dataset.feature] = input.checked;
  }
  setStatus('ac-set-status', 'Saving…');
  el('ac-set-save').disabled = true;
  try {
    const saved = await api('/api/auth/settings', { method: 'POST', headers: jsonHeaders, body: JSON.stringify(body) });
    invalidateSettings();
    features = await api('/api/auth/features', { method: 'POST', headers: jsonHeaders, body: JSON.stringify(nextFeatures) });
    await api('/api/auth/open-signup', {
      method: 'PUT', headers: jsonHeaders, body: JSON.stringify({ enabled: el('ac-set-signup').checked }),
    });
    fill(saved && typeof saved === 'object' ? saved : await api('/api/auth/settings'));
    renderFeatures();
    setStatus('ac-set-status', 'Saved.', 'ok');
  } catch (err) {
    setStatus('ac-set-status', err.message, 'error');
  } finally {
    el('ac-set-save').disabled = false;
  }
}

export async function initSettings(status) {
  el('ac-set-save').addEventListener('click', save);
  const [settings, feats] = await Promise.all([api('/api/auth/settings'), api('/api/auth/features')]);
  features = feats || {};
  fill(settings || {});
  renderFeatures();
  el('ac-set-signup').checked = !!(status && status.signup_enabled);
}
