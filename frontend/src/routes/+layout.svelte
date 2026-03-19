<script>
  import '../app.css';
  import { activeTab, notification } from '$lib/stores.js';
  import Chat from '$lib/components/Chat.svelte';
  import LLMConfig from '$lib/components/LLMConfig.svelte';
  import SkillList from '$lib/components/SkillList.svelte';
  import Documents from '$lib/components/Documents.svelte';
  import FactInfo from '$lib/components/FactInfo.svelte';
  import ConvSidebar from '$lib/components/ConvSidebar.svelte';

  const tabs = [
    { id: 'chat',      label: '💬 对话' },
    { id: 'skills',    label: '🔧 Skill' },
    { id: 'documents', label: '📁 文档' },
    { id: 'facts',     label: '🗂 事实信息' },
    { id: 'llm',       label: '⚙️ LLM 配置' },
  ];
</script>

<div class="app">
  <!-- Left nav -->
  <nav class="nav">
    <div class="logo">NextAgent<br><span>Doc Assistant</span></div>
    {#each tabs as tab}
      <button
        class="nav-btn {$activeTab === tab.id ? 'active' : ''}"
        on:click={() => activeTab.set(tab.id)}
      >
        {tab.label}
      </button>
    {/each}
  </nav>

  <!-- Conversation sidebar (only in chat view) -->
  {#if $activeTab === 'chat'}
    <aside class="sidebar-panel">
      <ConvSidebar />
    </aside>
  {/if}

  <!-- Main content -->
  <main class="main">
    {#if $activeTab === 'chat'}      <Chat />
    {:else if $activeTab === 'skills'}   <SkillList />
    {:else if $activeTab === 'documents'} <Documents />
    {:else if $activeTab === 'facts'}    <FactInfo />
    {:else if $activeTab === 'llm'}     <LLMConfig />
    {/if}
  </main>
</div>

<!-- Toast notification -->
{#if $notification}
  <div class="toast toast-{$notification.type}">{$notification.text}</div>
{/if}

<style>
.app { display: flex; height: 100vh; overflow: hidden; }

.nav {
  width: 160px; flex-shrink: 0;
  background: var(--surface); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; padding: 12px 8px; gap: 4px;
}
.logo { font-weight: 700; font-size: 14px; color: var(--text); padding: 8px 8px 16px; line-height: 1.4; }
.logo span { font-weight: 400; font-size: 11px; color: var(--text-muted); }
.nav-btn {
  background: none; color: var(--text-muted); text-align: left;
  padding: 9px 10px; border-radius: 6px; font-size: 13px;
}
.nav-btn:hover { background: var(--surface2); color: var(--text); }
.nav-btn.active { background: var(--surface2); color: var(--text); font-weight: 500; }

.sidebar-panel {
  width: 200px; flex-shrink: 0;
  background: var(--surface); border-right: 1px solid var(--border);
  overflow: hidden;
}

.main { flex: 1; overflow: hidden; display: flex; flex-direction: column; }

.toast {
  position: fixed; bottom: 20px; right: 20px; z-index: 200;
  padding: 10px 18px; border-radius: 8px; font-size: 13px; font-weight: 500;
  animation: slide-in 0.2s ease;
}
.toast-success { background: #1a3d2e; color: #3ecf8e; border: 1px solid #3ecf8e44; }
.toast-error   { background: #3d1a1e; color: #e05c6a; border: 1px solid #e05c6a44; }
.toast-info    { background: var(--surface2); color: var(--text); border: 1px solid var(--border); }

@keyframes slide-in { from { transform: translateY(12px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
</style>
