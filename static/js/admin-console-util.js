// Shared helpers for the Admin Console modules.

export const el = (id) => document.getElementById(id);

export function node(tag, text, className) {
  const n = document.createElement(tag);
  if (text != null) n.textContent = text;
  if (className) n.className = className;
  return n;
}

export async function api(path, options = {}) {
  const res = await fetch(path, { credentials: 'same-origin', ...options });
  let body = null;
  try { body = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const detail = body && (body.detail || body.error);
    throw new Error((typeof detail === 'string' && detail) || `Request failed (${res.status})`);
  }
  return body;
}

export function setStatus(id, text, kind = '') {
  const box = el(id);
  if (!box) return;
  box.className = `status${kind ? ' ' + kind : ''}`;
  box.textContent = text || '';
}

export const jsonHeaders = { 'Content-Type': 'application/json' };
