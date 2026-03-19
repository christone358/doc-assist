/** Thin wrapper around the backend REST/WS API. */

const BASE = '/api/v1';

async function req(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.status === 204 ? null : res.json();
}

// ── Conversations ──────────────────────────────────────────────────────────
export const conversations = {
  list:   ()           => req('GET',    '/conversations'),
  create: (body)       => req('POST',   '/conversations', body),
  get:    (id)         => req('GET',    `/conversations/${id}`),
  delete: (id)         => req('DELETE', `/conversations/${id}`),
};

// ── Chat (non-streaming) ───────────────────────────────────────────────────
export const chat = {
  send: (conversation_id, message) =>
    req('POST', '/chat', { conversation_id, message }),
};

// ── Skills ─────────────────────────────────────────────────────────────────
export const skills = {
  list: ()     => req('GET', '/skills'),
  get:  (id)   => req('GET', `/skills/${id}`),
};

// ── LLM configs ────────────────────────────────────────────────────────────
export const llmConfigs = {
  list:       ()         => req('GET',    '/llm/configs'),
  create:     (body)     => req('POST',   '/llm/configs', body),
  update:     (id, body) => req('PATCH',  `/llm/configs/${id}`, body),
  delete:     (id)       => req('DELETE', `/llm/configs/${id}`),
  setDefault: (id)       => req('POST',   `/llm/configs/${id}/set-default`),
  test:       (id)       => req('POST',   `/llm/configs/${id}/test`),
};

// ── Documents ──────────────────────────────────────────────────────────────
export const documents = {
  list:       (doc_type)              => req('GET', `/documents${doc_type ? `?doc_type=${doc_type}` : ''}`),
  versions:   (doc_type, doc_name)    => req('GET', `/documents/${doc_type}/${doc_name}/versions`),
  latest:     (doc_type, doc_name)    => req('GET', `/documents/${doc_type}/${doc_name}/latest`),
  getVersion: (doc_type, doc_name, date, ver) =>
                                         req('GET', `/documents/${doc_type}/${doc_name}/${date}/${ver}`),
};

// ── Project fact information ───────────────────────────────────────────────
export const factInfo = {
  list:   (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return req('GET', `/fact-info${q ? '?' + q : ''}`);
  },
  get: (id) => req('GET', `/fact-info/${id}`),
};

// ── WebSocket helper ───────────────────────────────────────────────────────
export function openChatSocket(conversationId, onMessage) {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${protocol}://${location.host}/ws/${conversationId}`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  ws.onerror   = (e) => console.error('WS error', e);
  return ws;
}
