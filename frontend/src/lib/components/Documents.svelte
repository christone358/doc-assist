<script>
  import { onMount } from 'svelte';
  import { docList, notify } from '$lib/stores.js';
  import { documents } from '$lib/api.js';

  let selectedDoc = null;
  let versions = [];
  let filterType = '';

  onMount(() => refresh());

  async function refresh() {
    const res = await documents.list(filterType || undefined);
    docList.set(res.documents || []);
  }

  async function selectDoc(doc) {
    selectedDoc = doc;
    const res = await documents.versions(doc.doc_type, doc.doc_name);
    versions = res.versions || [];
  }

  function copyPath(path) {
    navigator.clipboard?.writeText(path);
    notify('success', '路径已复制');
  }

  const typeConfig = {
    requirements: { color: '#6366f1', bg: 'rgba(99,102,241,0.1)', label: '需求规格' },
    design:       { color: '#10b981', bg: 'rgba(16,185,129,0.1)', label: '设计方案' },
    api:          { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  label: 'API 文档' },
    'test-plan':  { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   label: '测试方案' },
    test:         { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   label: '测试方案' },
    'user-manual': { color: '#0ea5e9', bg: 'rgba(14,165,233,0.1)', label: '用户手册' },
    'user-guide': { color: '#0ea5e9', bg: 'rgba(14,165,233,0.1)', label: '用户手册' },
    general:      { color: '#64748b', bg: 'rgba(100,116,139,0.1)', label: '通用文档' },
  };
  function getType(t, fallbackLabel = t) {
    return typeConfig[t] || { color: '#64748b', bg: 'rgba(100,116,139,0.1)', label: fallbackLabel };
  }
</script>

<div class="page">
  <div class="page-header">
    <h2>文档版本管理</h2>
    <div class="filter">
      <span class="material-symbols-outlined" style="font-size:16px;color:var(--text-muted);">filter_list</span>
      <select bind:value={filterType} on:change={refresh}>
        <option value="">全部类型</option>
        <option value="requirements">需求规格</option>
        <option value="design">设计方案</option>
        <option value="api">API 文档</option>
        <option value="test-plan">测试方案</option>
        <option value="user-manual">用户手册</option>
      </select>
    </div>
  </div>

  {#if $docList.length === 0}
    <div class="empty">
      <span class="material-symbols-outlined" style="font-size:36px;color:var(--dividers);font-variation-settings:'FILL' 0,'wght' 300;">folder_open</span>
      <p>暂无生成的文档</p>
      <p class="empty-hint">通过对话生成文档后，将在此处显示</p>
    </div>
  {:else}
    <div class="doc-list">
      {#each $docList as doc}
        {@const tc = getType(doc.doc_type, doc.doc_type_label)}
        <div class="doc-row {selectedDoc?.doc_name === doc.doc_name && selectedDoc?.doc_type === doc.doc_type ? 'selected' : ''}">
          <div class="doc-icon-wrap" style="background:{tc.bg}">
            <span class="material-symbols-outlined" style="font-size:18px;color:{tc.color};font-variation-settings:'FILL' 1,'wght' 400;">description</span>
          </div>
          <div class="doc-info">
            <div class="doc-name">{doc.doc_name}</div>
            <div class="doc-meta">
              <span class="type-badge" style="background:{tc.bg};color:{tc.color}">{doc.doc_type_label || tc.label}</span>
              <span class="meta-sep">·</span>
              <span class="meta-text">v{doc.latest_version}</span>
              <span class="meta-sep">·</span>
              <span class="meta-text">{doc.latest_date}</span>
              {#if doc.aliases?.length > 1}
                <span class="meta-sep">·</span>
                <span class="meta-text">{doc.aliases.length} 个别名</span>
              {/if}
            </div>
          </div>
          <div class="doc-path-text">{doc.path}</div>
          <div class="doc-actions">
            <button class="btn-ghost sm" on:click={() => selectDoc(doc)}>
              <span class="material-symbols-outlined" style="font-size:14px;">history</span>
              版本历史
            </button>
            <button class="btn-ghost sm" on:click={() => copyPath(doc.path)}>
              <span class="material-symbols-outlined" style="font-size:14px;">content_copy</span>
              复制路径
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

{#if selectedDoc}
  <div class="overlay" on:click|self={() => { selectedDoc = null; versions = []; }}>
    <div class="modal">
      <div class="modal-header">
        <div>
          <h3>{selectedDoc.doc_name}</h3>
          <span class="modal-subtitle">版本历史</span>
        </div>
        <button class="btn-ghost" on:click={() => { selectedDoc = null; versions = []; }}>
          <span class="material-symbols-outlined" style="font-size:16px;">close</span>
        </button>
      </div>
      {#if versions.length === 0}
        <p class="empty-modal">暂无版本记录</p>
      {:else}
        <div class="version-list">
          {#each versions as v}
            <div class="version-row">
              <div class="ver-badge">v{v.version}</div>
              <div class="ver-info">
                <span class="ver-date">{v.date}</span>
                <span class="ver-path">{v.path}</span>
              </div>
              <button class="btn-ghost sm" on:click={() => copyPath(v.path)}>
                <span class="material-symbols-outlined" style="font-size:14px;">content_copy</span>
              </button>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
.page { padding: 28px 32px; }

.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
h2 { font-family: var(--font-headline); font-size: 20px; font-weight: 700; color: var(--text); }

.filter {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--high);
  border-radius: var(--radius);
  padding: 6px 12px;
}
.filter select {
  background: transparent;
  border: none;
  width: 140px;
  padding: 0;
  font-size: 13px;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-top: 60px;
  text-align: center;
}
.empty p { font-size: 15px; font-weight: 500; color: var(--text); }
.empty-hint { font-size: 13px !important; font-weight: 400 !important; color: var(--text-muted) !important; }

.doc-list { display: flex; flex-direction: column; gap: 10px; }

.doc-row {
  display: flex;
  align-items: center;
  gap: 14px;
  background: var(--lowest);
  border-radius: var(--radius-lg);
  padding: 14px 18px;
  box-shadow: var(--shadow-soft);
  transition: box-shadow 0.2s;
}
.doc-row:hover { box-shadow: var(--shadow-float); }
.doc-row.selected { outline: 2px solid var(--primary); outline-offset: -1px; }

.doc-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.doc-info { flex: 1; min-width: 0; }
.doc-name { font-weight: 600; font-size: 14px; color: var(--text); margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.doc-meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.type-badge { padding: 2px 8px; border-radius: var(--radius-sm); font-size: 11px; font-weight: 600; }
.meta-sep { color: var(--dividers); }
.meta-text { font-size: 12px; color: var(--text-muted); }

.doc-path-text {
  font-family: monospace;
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 220px;
  flex-shrink: 0;
}

.doc-actions { display: flex; gap: 6px; flex-shrink: 0; }
.sm { display: inline-flex; align-items: center; gap: 4px; padding: 5px 10px; font-size: 12px; }

/* Modal */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(15,23,42,0.4);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: var(--lowest);
  border-radius: var(--radius-xl);
  padding: 28px;
  width: 600px;
  max-width: 95vw;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: var(--shadow-float);
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}
.modal-header h3 { font-family: var(--font-headline); font-size: 16px; font-weight: 700; color: var(--text); }
.modal-subtitle { font-size: 12px; color: var(--text-muted); margin-top: 2px; display: block; }
.empty-modal { color: var(--text-muted); text-align: center; padding: 20px 0; }

.version-list { display: flex; flex-direction: column; gap: 8px; }
.version-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  background: var(--base);
  border-radius: var(--radius);
}
.ver-badge {
  background: var(--primary-surface);
  color: var(--primary);
  border-radius: var(--radius-sm);
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}
.ver-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.ver-date { font-size: 12px; color: var(--text); font-weight: 500; }
.ver-path { font-family: monospace; font-size: 11px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
