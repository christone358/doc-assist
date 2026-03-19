<script>
  import { onMount } from 'svelte';
  import { activeConvId, convList, convRefresh, notify } from '$lib/stores.js';
  import { conversations } from '$lib/api.js';

  onMount(refresh);

  // Refresh list whenever a new conversation is created (skip initial value 0)
  $: if ($convRefresh > 0) refresh();

  export async function refresh() {
    const res = await conversations.list();
    convList.set(res.conversations || []);
  }

  async function open(id) {
    activeConvId.set(id);
  }

  async function remove(e, id) {
    e.stopPropagation();
    if (!confirm('删除该对话？')) return;
    await conversations.delete(id);
    if ($activeConvId === id) activeConvId.set(null);
    await refresh();
    notify('success', '对话已删除');
  }

  function formatDate(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false,
    });
  }
</script>

<div class="sidebar">
  <div class="sidebar-title">对话记录</div>
  {#if $convList.length === 0}
    <div class="empty">暂无对话</div>
  {:else}
    {#each $convList as conv}
      <button
        class="conv-item {$activeConvId === conv.id ? 'active' : ''}"
        on:click={() => open(conv.id)}
      >
        <div class="conv-name">{conv.name}</div>
        <div class="conv-meta">{formatDate(conv.updated_at)}</div>
        <button class="del-btn" on:click={(e) => remove(e, conv.id)}>✕</button>
      </button>
    {/each}
  {/if}
</div>

<style>
.sidebar { display: flex; flex-direction: column; height: 100%; overflow-y: auto; padding: 8px; }
.sidebar-title { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: .05em; padding: 6px 8px; }
.empty { color: var(--text-muted); font-size: 12px; padding: 12px 8px; }
.conv-item {
  display: flex; flex-direction: column; gap: 2px;
  padding: 8px 10px; border-radius: 6px; cursor: pointer;
  background: none; color: var(--text); text-align: left;
  border: 1px solid transparent; position: relative;
}
.conv-item:hover { background: var(--surface2); }
.conv-item.active { background: var(--surface2); border-color: var(--border); }
.conv-name { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 160px; }
.conv-meta { font-size: 11px; color: var(--text-muted); }
.del-btn {
  position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  background: none; color: var(--text-muted); font-size: 11px; padding: 2px 4px;
  opacity: 0;
}
.conv-item:hover .del-btn { opacity: 1; }
.del-btn:hover { color: var(--danger); }
</style>
