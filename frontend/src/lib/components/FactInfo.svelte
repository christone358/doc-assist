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
  const layerColor = { manifest: '#4f6ef7', core: '#3ecf8e', design: '#f5a623' };
</script>

<div class="page">
  <div class="page-header">
    <h2>项目事实信息</h2>
    <span class="hint-text">由人工维护 · Agent 只读</span>
  </div>

  <div class="toolbar">
    <select bind:value={layer} on:change={load}>
      <option value="">全部层级</option>
      <option value="manifest">清单层</option>
      <option value="core">核心信息层</option>
      <option value="design">设计开发层</option>
    </select>
    <input bind:value={keyword} placeholder="关键词搜索…" on:input={load} />
  </div>

  {#if items.length === 0}
    <div class="empty">
      <p>暂无项目事实信息。</p>
      <p>请在 <code>project-facts/</code> 目录下按三层结构添加信息。</p>
    </div>
  {:else}
    <div class="items-list">
      {#each items as item}
        <button class="item-row {selected?.id === item.id ? 'active' : ''}" on:click={() => select(item)}>
          <span class="layer-dot" style="background:{layerColor[item.layer] || '#666'}"></span>
          <span class="item-name">{item.name || item.id}</span>
          <span class="tag">{layerLabel(item.layer)}</span>
        </button>
      {/each}
    </div>
  {/if}
</div>

{#if selectedDetail}
  <div class="detail-panel">
    <div class="detail-header">
      <div>
        <div class="d-name">{selectedDetail.name || selectedDetail.id}</div>
        <span class="tag">{layerLabel(selectedDetail.layer)}</span>
      </div>
      <button class="btn-ghost" on:click={() => { selected = null; selectedDetail = null; }}>关闭</button>
    </div>
    <div class="detail-content">{selectedDetail.content || '（无内容）'}</div>
  </div>
{/if}

<style>
.page { padding: 20px; }
.page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
h2 { font-size: 18px; font-weight: 600; }
.hint-text { color: var(--text-muted); font-size: 12px; }
.toolbar { display: flex; gap: 10px; margin-bottom: 16px; }
.toolbar select { width: 160px; }
.toolbar input { flex: 1; }
.empty { color: var(--text-muted); text-align: center; margin-top: 40px; line-height: 2.2; }
.empty code { background: var(--surface2); padding: 2px 6px; border-radius: 4px; }

.items-list { display: flex; flex-direction: column; gap: 4px; }
.item-row {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  text-align: left; cursor: pointer;
}
.item-row:hover { border-color: var(--accent); }
.item-row.active { border-color: var(--accent); background: var(--surface2); }
.layer-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.item-name { flex: 1; font-size: 13px; }

.detail-panel {
  position: fixed; right: 0; top: 0; bottom: 0; width: 400px;
  background: var(--surface); border-left: 1px solid var(--border);
  display: flex; flex-direction: column; z-index: 50;
}
.detail-header { display: flex; justify-content: space-between; align-items: flex-start; padding: 16px; border-bottom: 1px solid var(--border); }
.d-name { font-weight: 600; font-size: 15px; margin-bottom: 4px; }
.detail-content { padding: 16px; overflow-y: auto; flex: 1; white-space: pre-wrap; font-size: 13px; line-height: 1.7; color: var(--text); }
</style>
