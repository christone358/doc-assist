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

  const typeColors = { requirements: '#4f6ef7', design: '#3ecf8e', api: '#f5a623', test: '#e05c6a' };
</script>

<div class="page">
  <div class="page-header">
    <h2>文档版本管理</h2>
    <div class="filter">
      <select bind:value={filterType} on:change={refresh}>
        <option value="">全部类型</option>
        <option value="requirements">需求规格</option>
        <option value="design">设计方案</option>
        <option value="api">API 文档</option>
        <option value="test">测试方案</option>
      </select>
    </div>
  </div>

  {#if $docList.length === 0}
    <div class="empty">暂无生成的文档。通过对话生成文档后，将在此处显示。</div>
  {:else}
    <table>
      <thead>
        <tr>
          <th>文档名称</th><th>类型</th><th>最新版本</th><th>日期</th><th>路径</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        {#each $docList as doc}
          <tr class="{selectedDoc?.doc_name === doc.doc_name ? 'selected' : ''}">
            <td>{doc.doc_name}</td>
            <td><span class="type-badge" style="background:{typeColors[doc.doc_type] || '#666'}22;color:{typeColors[doc.doc_type] || '#888'}">{doc.doc_type}</span></td>
            <td>v{doc.latest_version}</td>
            <td>{doc.latest_date}</td>
            <td class="path-cell">
              <span class="path-text">{doc.path}</span>
            </td>
            <td>
              <button class="btn-ghost sm" on:click={() => selectDoc(doc)}>版本历史</button>
              <button class="btn-ghost sm" on:click={() => copyPath(doc.path)}>复制路径</button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

{#if selectedDoc}
  <div class="overlay" on:click|self={() => { selectedDoc = null; versions = []; }}>
    <div class="modal">
      <div class="modal-header">
        <h3>{selectedDoc.doc_name} — 版本历史</h3>
        <button class="btn-ghost" on:click={() => { selectedDoc = null; versions = []; }}>关闭</button>
      </div>
      {#if versions.length === 0}
        <p class="empty">暂无版本记录</p>
      {:else}
        <table>
          <thead><tr><th>日期</th><th>版本</th><th>路径</th><th>操作</th></tr></thead>
          <tbody>
            {#each versions as v}
              <tr>
                <td>{v.date}</td>
                <td>v{v.version}</td>
                <td class="path-cell"><span class="path-text">{v.path}</span></td>
                <td><button class="btn-ghost sm" on:click={() => copyPath(v.path)}>复制路径</button></td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
  </div>
{/if}

<style>
.page { padding: 20px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
h2 { font-size: 18px; font-weight: 600; }
.filter select { width: 160px; }
.empty { color: var(--text-muted); text-align: center; margin-top: 40px; }

table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 8px 10px; color: var(--text-muted); border-bottom: 1px solid var(--border); }
td { padding: 8px 10px; border-bottom: 1px solid var(--border); }
tr.selected td { background: var(--surface2); }
.type-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.path-cell { max-width: 240px; overflow: hidden; }
.path-text { font-family: monospace; font-size: 11px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
.sm { padding: 3px 8px; font-size: 12px; }

.overlay { position: fixed; inset: 0; background: rgba(0,0,0,.6); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 24px; width: 640px; max-width: 95vw; max-height: 80vh; overflow-y: auto; }
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.modal h3 { font-size: 15px; font-weight: 600; }
</style>
