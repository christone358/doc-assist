import { writable, derived } from 'svelte/store';

// Active conversation ID
export const activeConvId = writable(null);

// All conversations (list view)
export const convList = writable([]);

// Messages in the active conversation
export const messages = writable([]);   // [{role, content, docs, ts}]

// Streaming status
export const streaming = writable(false);

// Current WebSocket instance
export const wsConn = writable(null);

// Available skills
export const skillList = writable([]);

// LLM configs
export const llmConfigList = writable([]);

// Documents (version management)
export const docList = writable([]);

// Navigation: 'chat' | 'skills' | 'llm' | 'documents' | 'facts'
export const activeTab = writable('chat');

// Trigger sidebar to refresh conversation list (increment to signal)
export const convRefresh = writable(0);
export function triggerConvRefresh() { convRefresh.update(n => n + 1); }

// Notification: {type:'success'|'error'|'info', text, id}
export const notification = writable(null);
let _notifTimer;
export function notify(type, text) {
  clearTimeout(_notifTimer);
  notification.set({ type, text, id: Date.now() });
  _notifTimer = setTimeout(() => notification.set(null), 3500);
}
