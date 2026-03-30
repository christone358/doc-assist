<script>
  import '../app.css';
  import { onMount } from 'svelte';
  import { activeTab, notification, convList, activeConvId, convRefresh, notify } from '$lib/stores.js';
  import { conversations } from '$lib/api.js';
  import Chat from '$lib/components/Chat.svelte';
  import LLMConfig from '$lib/components/LLMConfig.svelte';
  import SkillList from '$lib/components/SkillList.svelte';
  import Documents from '$lib/components/Documents.svelte';
  import FactInfo from '$lib/components/FactInfo.svelte';

  // Top nav tabs (LLM config moved to bottom)
  const tabs = [
    { id: 'chat',      label: '新对话',   icon: 'chat_bubble',  action: newChat },
    { id: 'skills',    label: 'Skill',    icon: 'extension',    action: null },
    { id: 'documents', label: '文档',     icon: 'folder_open',  action: null },
    { id: 'facts',     label: '事实信息', icon: 'auto_stories', action: null },
  ];

  // ── Conversation list ──────────────────────────────────────────────────────

  async function loadConvList() {
    try {
      const res = await conversations.list();
      convList.set(res.conversations || []);
    } catch (e) {
      // silent — no LLM config yet is expected on first load
    }
  }

  onMount(loadConvList);
  $: if ($convRefresh > 0) loadConvList();

  function groupByDate(list) {
    const today = new Date();
    const todayStr = today.toDateString();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    const yesterdayStr = yesterday.toDateString();

    const groups = { today: [], yesterday: [], earlier: [] };
    for (const c of list) {
      const d = new Date(c.updated_at).toDateString();
      if (d === todayStr)        groups.today.push(c);
      else if (d === yesterdayStr) groups.yesterday.push(c);
      else                       groups.earlier.push(c);
    }
    return groups;
  }

  $: grouped = groupByDate($convList);

  async function openConv(id) {
    activeConvId.set(id);
    activeTab.set('chat');
  }

  async function removeConv(e, id) {
    e.stopPropagation();
    if (!confirm('删除该对话？')) return;
    await conversations.delete(id);
    if ($activeConvId === id) activeConvId.set(null);
    await loadConvList();
    notify('success', '对话已删除');
  }

  async function newChat() {
    activeConvId.set(null);
    activeTab.set('chat');
  }
</script>

<div class="app">
  <!-- ── Left Navigation ── -->
  <nav class="nav">

    <!-- Zone 1: Logo + main menu (fixed top) -->
    <div class="nav-top">
      <div class="logo">
        <div class="logo-icon">
          <span class="material-symbols-outlined" style="font-size:18px;color:#fff;font-variation-settings:'FILL' 1,'wght' 600;">auto_awesome</span>
        </div>
        <div class="logo-text">
          <span class="logo-name">NextAgent</span>
          <span class="logo-sub">Doc Assistant</span>
        </div>
      </div>

      <div class="nav-menu">
        {#each tabs as tab}
          {@const isActive = tab.id === 'chat'
            ? ($activeTab === 'chat' && !$activeConvId)
            : $activeTab === tab.id}
          <button
            class="nav-btn {isActive ? 'active' : ''}"
            on:click={() => tab.action ? tab.action() : activeTab.set(tab.id)}
          >
            <span class="material-symbols-outlined nav-icon">{tab.icon}</span>
            <span class="nav-label">{tab.label}</span>
          </button>
        {/each}
      </div>
    </div>

    <!-- Zone 2: Conversation list (scrollable middle) -->
    <div class="nav-convs">
      <div class="convs-section-title">对话</div>
      {#if $convList.length === 0}
        <div class="convs-empty">暂无对话</div>
      {:else}
        {#if grouped.today.length > 0}
          <div class="date-group">
            <span class="date-label">今天</span>
            {#each grouped.today as conv}
              <button
                class="conv-item {$activeConvId === conv.id && $activeTab === 'chat' ? 'active' : ''}"
                on:click={() => openConv(conv.id)}
              >
                <span class="conv-name">{conv.name}</span>
                <button class="conv-del" on:click={(e) => removeConv(e, conv.id)}>
                  <span class="material-symbols-outlined" style="font-size:13px;">close</span>
                </button>
              </button>
            {/each}
          </div>
        {/if}

        {#if grouped.yesterday.length > 0}
          <div class="date-group">
            <span class="date-label">昨天</span>
            {#each grouped.yesterday as conv}
              <button
                class="conv-item {$activeConvId === conv.id && $activeTab === 'chat' ? 'active' : ''}"
                on:click={() => openConv(conv.id)}
              >
                <span class="conv-name">{conv.name}</span>
                <button class="conv-del" on:click={(e) => removeConv(e, conv.id)}>
                  <span class="material-symbols-outlined" style="font-size:13px;">close</span>
                </button>
              </button>
            {/each}
          </div>
        {/if}

        {#if grouped.earlier.length > 0}
          <div class="date-group">
            <span class="date-label">更早</span>
            {#each grouped.earlier as conv}
              <button
                class="conv-item {$activeConvId === conv.id && $activeTab === 'chat' ? 'active' : ''}"
                on:click={() => openConv(conv.id)}
              >
                <span class="conv-name">{conv.name}</span>
                <button class="conv-del" on:click={(e) => removeConv(e, conv.id)}>
                  <span class="material-symbols-outlined" style="font-size:13px;">close</span>
                </button>
              </button>
            {/each}
          </div>
        {/if}
      {/if}
    </div>

    <!-- Zone 3: Settings (fixed bottom) -->
    <div class="nav-bottom">
      <button
        class="nav-btn {$activeTab === 'llm' ? 'active' : ''}"
        on:click={() => activeTab.set('llm')}
      >
        <span class="material-symbols-outlined nav-icon">settings</span>
        <span class="nav-label">LLM 配置</span>
      </button>
    </div>

  </nav>

  <!-- ── Main Content ── -->
  <main class="main">
    {#if $activeTab === 'chat'}      <Chat />
    {:else if $activeTab === 'skills'}   <SkillList />
    {:else if $activeTab === 'documents'} <Documents />
    {:else if $activeTab === 'facts'}    <FactInfo />
    {:else if $activeTab === 'llm'}     <LLMConfig />
    {/if}
    <slot />
  </main>
</div>

<!-- Toast notification -->
{#if $notification}
  <div class="toast toast-{$notification.type}">{$notification.text}</div>
{/if}

<style>
.app { display: flex; height: 100vh; overflow: hidden; background: var(--base); }

/* ════════════════════════════════
   Left Navigation — three zones
   ════════════════════════════════ */
.nav {
  width: 220px;
  flex-shrink: 0;
  background: var(--base);
  display: flex;
  flex-direction: column;
  /* No border — depth via bg shift with main */
}

/* ── Zone 1: Top (logo + menu) ── */
.nav-top {
  flex-shrink: 0;
  padding: 20px 12px 8px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 4px 16px;
}
.logo-icon {
  width: 34px;
  height: 34px;
  background: var(--primary);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(99,102,241,0.35);
}
.logo-text { display: flex; flex-direction: column; gap: 1px; }
.logo-name { font-family: var(--font-headline); font-weight: 700; font-size: 13px; color: var(--text); line-height: 1.2; }
.logo-sub  { font-size: 10px; color: var(--text-muted); }

.nav-menu { display: flex; flex-direction: column; gap: 2px; }

/* ── Zone 2: Middle (conversation list) ── */
.nav-convs {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.convs-section-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  padding: 4px 0 4px 12px;
}

.convs-empty { font-size: 12px; color: var(--text-muted); padding: 4px 0 4px 12px; }

.date-group { margin-bottom: 4px; }
.date-label {
  display: block;
  font-size: 10px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 8px 0 2px 12px;
}

.conv-item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 9px 0 9px 12px;
  border-radius: var(--radius);
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  gap: 10px;
}
.conv-item:hover { background: var(--lowest); color: var(--text); }
.conv-item.active { background: var(--lowest); color: var(--primary); box-shadow: var(--shadow-soft); }

.conv-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}
.conv-del {
  flex-shrink: 0;
  background: none;
  border: none;
  color: var(--text-muted);
  padding: 1px;
  border-radius: var(--radius-sm);
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  display: flex;
  align-items: center;
}
.conv-item:hover .conv-del { opacity: 1; }
.conv-del:hover { color: var(--danger); background: rgba(239,68,68,0.1); }

/* ── Zone 3: Bottom (settings) ── */
.nav-bottom {
  flex-shrink: 0;
  padding: 8px 12px 16px;
}

/* ── Shared nav button ── */
.nav-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  background: none;
  color: var(--text-muted);
  text-align: left;
  padding: 9px 12px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 500;
  width: 100%;
  border: none;
}
.nav-btn:hover { background: var(--lowest); color: var(--text); }
.nav-btn.active {
  background: var(--lowest);
  color: var(--primary);
  box-shadow: var(--shadow-soft);
}
.nav-btn.active .nav-icon { font-variation-settings: 'FILL' 1, 'wght' 500; }
.nav-icon { font-size: 18px; flex-shrink: 0; }
.nav-label { flex: 1; }

/* ════════════════════════════════
   Main Content
   ════════════════════════════════ */
.main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--lowest);
  border-radius: var(--radius-lg) 0 0 var(--radius-lg);
  box-shadow: var(--shadow-panel);
}

/* ── Toast ── */
.toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 200;
  padding: 10px 20px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 500;
  box-shadow: var(--shadow-float);
  animation: slide-in 0.2s ease;
}
.toast-success { background: var(--lowest); color: var(--success); border-left: 3px solid var(--success); }
.toast-error   { background: var(--lowest); color: var(--danger);  border-left: 3px solid var(--danger); }
.toast-info    { background: var(--lowest); color: var(--text);    border-left: 3px solid var(--primary); }

@keyframes slide-in { from { transform: translateY(12px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
</style>
