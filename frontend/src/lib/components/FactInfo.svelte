<script>
  import { onMount } from 'svelte';
  import { factInfo } from '$lib/api.js';

  let items = [];
  let selected = null;
  let selectedDetail = null;
  let layer = '';
  let keyword = '';

  onMount(() => load());

  async function load() {
    const params = {};
    if (layer) params.layer = layer;
    if (keyword) params.keyword = keyword;
    const res = await factInfo.list(params);
    items = res.items || [];
  }

  async function select(item) {
    selected = item;
    const res = await factInfo.get(item.id);
    selectedDetail = res;
  }

  function layerLabel(l) {
    return { manifest: '清单层', core: '核心信息层', design: '设计开发层' }[l] || l;
  }

  const layerConfig = {
    manifest: { color: '#6366f1', bg: 'rgba(99,102,241,0.1)' },
    core:     { color: '#10b981', bg: 'rgba(16,185,129,0.1)' },
    design:   { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)' },
  };
  function getLayer(l) { return layerConfig[l] || { color: '#64748b', bg: 'rgba(100,116,139,0.1)' }; }
</script>

<div class="page">
  <div class="page-header">
    <div>
      <h2>项目事实信息</h2>
      <p class="page-subtitle">由人工维护 · Agent 只读</p>
    </div>
  </div>

  <div class="toolbar">
    <div class="filter-wrap">
      <span class="material-symbols-outlined" style="font-size:16px;color:var(--text-muted);">layers</span>
      <select bind:value={layer} on:change={load}>
        <option value="">全部层级</option>
        <option value="manifest">清单层</option>
        <option value="core">核心信息层</option>
        <option value="design">设计开发层</option>
      </select>
    </div>
    <div class="search-wrap">
      <span class="material-symbols-outlined" style="font-size:16px;color:var(--text-muted);">search</span>
      <input bind:value={keyword} placeholder="关键词搜索…" on:input={load} style="background:transparent;border:none;padding:0 4px;" />
    </div>
  </div>

  {#if items.length === 0}
    <div class="empty">
      <span class="material-symbols-outlined" style="font-size:36px;color:var(--dividers);font-variation-settings:'FILL' 0,'wght' 300;">auto_stories</span>
      <p>暂无项目事实信息</p>
      <p class="empty-hint">请在 <code>project-facts/</code> 目录下按三层结构添加信息</p>
    </div>
  {:else}
    <div class="items-list">
      {#each items as item}
        {@const lc = getLayer(item.layer)}
        <button class="item-row {selected?.id === item.id ? 'active' : ''}" on:click={() => select(item)}>
          <div class="layer-icon" style="background:{lc.bg}">
            <span class="layer-dot" style="background:{lc.color}"></span>
          </div>
          <span class="item-name">{item.name || item.id}</span>
          <span class="layer-tag" style="background:{lc.bg};color:{lc.color}">{layerLabel(item.layer)}</span>
          <span class="material-symbols-outlined chevron" style="font-size:16px;">chevron_right</span>
        </button>
      {/each}
    </div>
  {/if}
</div>

{#if selectedDetail}
  <div class="detail-panel">
    <div class="detail-header">
      <div class="detail-title-wrap">
        <div class="detail-layer-icon" style="background:{getLayer(selectedDetail.layer).bg}">
          <span class="layer-dot" style="background:{getLayer(selectedDetail.layer).color}"></span>
        </div>
        <div>
          <div class="d-name">{selectedDetail.name || selectedDetail.id}</div>
          <span class="layer-tag" style="background:{getLayer(selectedDetail.layer).bg};color:{getLayer(selectedDetail.layer).color}">{layerLabel(selectedDetail.layer)}</span>
        </div>
      </div>
      <button class="btn-ghost" on:click={() => { selected = null; selectedDetail = null; }}>
        <span class="material-symbols-outlined" style="font-size:16px;">close</span>
      </button>
    </div>
    <div class="detail-content">{selectedDetail.content || '（无内容）'}</div>
  </div>
{/if}

<style>
.page { padding: 28px 32px; }

.page-header { margin-bottom: 20px; }
h2 { font-family: var(--font-headline); font-size: 20px; font-weight: 700; color: var(--text); }
.page-subtitle { font-size: 12px; color: var(--text-muted); margin-top: 3px; }

.toolbar { display: flex; gap: 12px; margin-bottom: 20px; }

.filter-wrap, .search-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--high);
  border-radius: var(--radius);
  padding: 8px 12px;
}
.filter-wrap select { background: transparent; border: none; width: 140px; padding: 0; font-size: 13px; }
.search-wrap { flex: 1; }
.search-wrap input { flex: 1; background: transparent !important; border: none !important; padding: 0 !important; font-size: 13px; }
.search-wrap input:focus { background: transparent !important; border: none !important; }

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
.empty code { background: var(--high); padding: 1px 6px; border-radius: var(--radius-sm); font-size: 12px; }

.items-list { display: flex; flex-direction: column; gap: 6px; }

.item-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--lowest);
  border-radius: var(--radius-lg);
  text-align: left;
  cursor: pointer;
  box-shadow: var(--shadow-soft);
  transition: box-shadow 0.2s;
  width: 100%;
}
.item-row:hover { box-shadow: var(--shadow-float); }
.item-row.active { outline: 2px solid var(--primary); outline-offset: -1px; }

.layer-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.layer-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.item-name { flex: 1; font-size: 14px; font-weight: 500; color: var(--text); }
.layer-tag { padding: 2px 8px; border-radius: var(--radius-sm); font-size: 11px; font-weight: 600; }
.chevron { color: var(--text-muted); flex-shrink: 0; }

/* Detail panel */
.detail-panel {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 420px;
  background: var(--lowest);
  display: flex;
  flex-direction: column;
  z-index: 50;
  box-shadow: var(--shadow-float);
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px;
  border-bottom: 1.5px solid var(--dividers);
}
.detail-title-wrap { display: flex; align-items: center; gap: 12px; flex: 1; }
.detail-layer-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.d-name { font-family: var(--font-headline); font-weight: 700; font-size: 15px; color: var(--text); margin-bottom: 4px; }
.detail-content {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.75;
  color: var(--text);
}
</style>
