import { writable, derived } from 'svelte/store';

// Active conversation ID
export const activeConvId = writable(null);

// All conversations (list view)
export const convList = writable([]);

function sortConversationsByUpdatedAt(list) {
  return [...list].sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
}

export function updateConversationSummary(conversationId, patch) {
  convList.update((list) => {
    let found = false;
    const next = list.map((conv) => {
      if (conv.id !== conversationId) return conv;
      found = true;
      return { ...conv, ...patch };
    });
    return found ? sortConversationsByUpdatedAt(next) : list;
  });
}

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

// Agent Observability Panel
// ObsEvent: { type: 'thinking'|'reflection'|'summary'|'skill'|'status'|'question'|'done'|'execution_event', content, extra, ts }
function createObsStore() {
  const { subscribe, update } = writable({ panelOpen: false, events: [], nodes: [] });

  function mergeTraceNode(nodes, node) {
    const existingIndex = nodes.findIndex((item) => item.node_id === node.node_id);
    if (existingIndex >= 0) {
      const next = [...nodes];
      next[existingIndex] = { ...next[existingIndex], ...node };
      return next.slice().sort((a, b) => {
        const orderA = a.created_order ?? Number.MAX_SAFE_INTEGER;
        const orderB = b.created_order ?? Number.MAX_SAFE_INTEGER;
        if (orderA !== orderB) return orderA - orderB;
        return String(a.created_at || '').localeCompare(String(b.created_at || ''));
      });
    }
    return [...nodes, node].sort((a, b) => {
      const orderA = a.created_order ?? Number.MAX_SAFE_INTEGER;
      const orderB = b.created_order ?? Number.MAX_SAFE_INTEGER;
      if (orderA !== orderB) return orderA - orderB;
      return String(a.created_at || '').localeCompare(String(b.created_at || ''));
    });
  }

  return {
    subscribe,
    openPanel: () => update(s => ({ ...s, panelOpen: true })),
    closePanel: () => update(s => ({ ...s, panelOpen: false })),
    togglePanel: () => update(s => ({ ...s, panelOpen: !s.panelOpen })),
    clearEvents: () => update(s => ({ ...s, events: [], nodes: [] })),
    setTrace: ({ nodes = [], events = [] }) => update(s => ({
      ...s,
      nodes: [...nodes].sort((a, b) => {
        const orderA = a.created_order ?? Number.MAX_SAFE_INTEGER;
        const orderB = b.created_order ?? Number.MAX_SAFE_INTEGER;
        if (orderA !== orderB) return orderA - orderB;
        return String(a.created_at || '').localeCompare(String(b.created_at || ''));
      }),
      events,
    })),
    addTraceNode: (node) => update(s => ({
      ...s,
      nodes: mergeTraceNode(s.nodes, node),
    })),
    addEvent: (event) => update(s => {
      // Merge consecutive chunked text events into a single timeline item
      if (
        ['thinking', 'reflection', 'summary'].includes(event.type) &&
        s.events.length > 0 &&
        s.events[s.events.length - 1].type === event.type
      ) {
        const updated = [...s.events];
        updated[updated.length - 1] = { ...updated[updated.length - 1], content: updated[updated.length - 1].content + event.content };
        return { ...s, events: updated };
      }
      return { ...s, events: [...s.events, { ...event, ts: event.ts || Date.now() }] };
    }),
  };
}
export const obsStore = createObsStore();
let _notifTimer;
export function notify(type, text) {
  clearTimeout(_notifTimer);
  notification.set({ type, text, id: Date.now() });
  _notifTimer = setTimeout(() => notification.set(null), 3500);
}
