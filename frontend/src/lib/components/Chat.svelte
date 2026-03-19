<script>
  import { onMount, onDestroy, tick } from 'svelte';
  import { activeConvId, messages, streaming, wsConn, notify, triggerConvRefresh } from '$lib/stores.js';
  import { conversations, openChatSocket } from '$lib/api.js';

  let inputText = '';
  let messagesEl;
  let ws = null;

  // React to activeConvId changes (sidebar click)
  // Use subscribe instead of $: to avoid Svelte reactive timing issues
  const unsubConvId = activeConvId.subscribe(id => {
    if (id) switchConversation(id);
    else { messages.set([]); ws?.close(); }
  });

  onMount(() => {
    // ConvSidebar's onMount will set convList; we just wait for user to click
    // If there's already an active conversation (e.g. after HMR), load it
    if ($activeConvId) switchConversation($activeConvId);
  });

  onDestroy(() => {
    unsubConvId();
    ws?.close();
    streaming.set(false);
  });

  let _currentConvId = null;

  async function switchConversation(id) {
    if (id === _currentConvId) return; // already loaded
    _currentConvId = id;
    streaming.set(false);   // before ws.close() so onclose sees $streaming===false
    currentAssistantMsg = null;
    ws?.close();
    const conv = await conversations.get(id);
    if (_currentConvId !== id) return; // switched again while loading
    const msgs = (conv.rounds || []).flatMap(r => [
      { role: 'user', content: r.user_input, ts: r.timestamp },
      {
        role: 'assistant',
        content: r.agent_response,
        docs: r.documents_generated,
        ts: r.timestamp,
        metaSkillId: r.skill_invoked || null,
        metaSkillName: r.skill_invoked || null,  // server stores id; display as-is
        metaSkillReason: r.llm_info?.skill_reason || null,
        metaUsage: r.llm_info?.total_tokens ? {
          prompt_tokens: r.llm_info.prompt_tokens,
          completion_tokens: r.llm_info.completion_tokens,
          total_tokens: r.llm_info.total_tokens,
        } : null,
      },
    ]);
    messages.set(msgs);
    ws = openSocket(id);
    wsConn.set(ws);
    await tick();
    scrollToBottom();
  }

  async function createConversation() {
    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    const name = `对话 ${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
    const res = await conversations.create({ name });
    _currentConvId = res.conversation_id;   // set before activeConvId to block subscribe re-entry
    activeConvId.set(res.conversation_id);
    messages.set([]);
    ws?.close();
    ws = openSocket(res.conversation_id);
    wsConn.set(ws);
    triggerConvRefresh();
    return res.conversation_id;
  }

  let currentAssistantMsg = null;

  // Unified WebSocket factory — attaches cleanup on unexpected close
  function openSocket(convId) {
    const sock = openChatSocket(convId, handleWSMessage);
    sock.addEventListener('close', () => {
      // Only act if streaming is still active (= unexpected close, not user-initiated)
      // stopStreaming / switchConversation both call streaming.set(false) synchronously
      // before ws.close(), so by the time this async event fires, $streaming is already false.
      if ($streaming) {
        streaming.set(false);
        if (currentAssistantMsg) {
          if (!currentAssistantMsg.content) currentAssistantMsg.content = '[连接中断]';
          messages.update(m => m);
          currentAssistantMsg = null;
        }
        notify('error', '连接已断开，请重试');
      }
    });
    return sock;
  }

  function handleWSMessage(data) {
    if (data.type === 'status' || data.type === 'skill_start') {
      // Build step text; for skill_start, append reason if present
      let stepText = data.type === 'skill_start'
        ? (data.content || `正在使用 Skill: ${data.skill_id}`)
        : data.content;
      if (data.type === 'skill_start' && data.reason) {
        stepText = `${stepText} · ${data.reason}`;
      }
      if (!currentAssistantMsg) {
        currentAssistantMsg = { role: 'assistant', content: '', docs: [], statusSteps: [stepText], ts: new Date().toISOString() };
        messages.update(m => [...m, currentAssistantMsg]);
      } else {
        currentAssistantMsg.statusSteps = [...(currentAssistantMsg.statusSteps || []), stepText];
        messages.update(m => m);
      }
    } else if (data.type === 'text') {
      if (!currentAssistantMsg) {
        currentAssistantMsg = { role: 'assistant', content: '', docs: [], statusSteps: [], ts: new Date().toISOString() };
        messages.update(m => [...m, currentAssistantMsg]);
      }
      currentAssistantMsg.content += data.content;
      messages.update(m => m);
      scrollToBottom();
    } else if (data.type === 'document') {
      if (currentAssistantMsg) {
        currentAssistantMsg.docs = [...(currentAssistantMsg.docs || []), data.document];
        messages.update(m => m);
      }
    } else if (data.type === 'done') {
      if (currentAssistantMsg) {
        currentAssistantMsg.metaSkillId = data.skill_id || null;
        currentAssistantMsg.metaSkillName = data.skill_name || null;
        currentAssistantMsg.metaSkillReason = data.skill_reason || null;
        currentAssistantMsg.metaUsage = data.usage || null;
        currentAssistantMsg.hasDraft = data.has_draft === true;
        messages.update(m => m);
      }
      streaming.set(false);
      currentAssistantMsg = null;
    } else if (data.type === 'error') {
      streaming.set(false);
      currentAssistantMsg = null;
      notify('error', data.content || '发生错误');
    }
  }

  function stopStreaming() {
    streaming.set(false);   // must come before ws.close() so onclose sees $streaming===false
    if (currentAssistantMsg) {
      if (!currentAssistantMsg.content) currentAssistantMsg.content = '[已中断]';
      messages.update(m => m);
      currentAssistantMsg = null;
    }
    ws?.close();
  }

  async function sendMessage() {
    const text = inputText.trim();
    if (!text || $streaming) return;

    // Auto-create conversation on first message if none exists
    if (!$activeConvId) {
      await createConversation();
    }

    inputText = '';
    streaming.set(true);
    currentAssistantMsg = null;

    messages.update(m => [...m, { role: 'user', content: text, ts: new Date().toISOString() }]);
    await scrollToBottom();

    // Reconnect WebSocket if closed/closing (e.g. after tab switch or disconnect)
    if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
      ws = openSocket($activeConvId);
      wsConn.set(ws);
    }

    const doSend = () => ws.send(JSON.stringify({ message: text }));

    if (ws.readyState === WebSocket.OPEN) {
      doSend();
    } else {
      // CONNECTING: wait for open before sending
      ws.addEventListener('open', doSend, { once: true });
      ws.addEventListener('error', () => {
        streaming.set(false);
        notify('error', '连接失败，请重试');
      }, { once: true });
    }

    await scrollToBottom();
  }

  function onKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  }

  async function scrollToBottom() {
    await tick();
    if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function newChat() {
    activeConvId.set(null);
    await createConversation();
  }

  function copyPath(path) {
    navigator.clipboard?.writeText(path);
    notify('success', '路径已复制');
  }

  // Draft save state: keyed by message timestamp
  let draftSaveState = {};  // { [ts]: 'idle' | 'saving' | 'saved' | 'error' }
  let draftSaveResult = {}; // { [ts]: { version, file_path } }

  async function saveDraft(msg) {
    const convId = $activeConvId;
    if (!convId || draftSaveState[msg.ts] === 'saving' || draftSaveState[msg.ts] === 'saved') return;
    draftSaveState[msg.ts] = 'saving';
    draftSaveState = { ...draftSaveState };
    try {
      const res = await fetch(`/api/v1/conversations/${convId}/save-draft`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      draftSaveResult[msg.ts] = data;
      draftSaveState[msg.ts] = 'saved';
      draftSaveState = { ...draftSaveState };
      notify('success', `已保存 v${data.version}`);
    } catch (e) {
      draftSaveState[msg.ts] = 'error';
      draftSaveState = { ...draftSaveState };
      notify('error', `保存失败：${e.message}`);
    }
  }
</script>

<div class="chat-root">
  <!-- Header -->
  <div class="chat-header">
    <span class="title">对话</span>
    <button class="btn-ghost" on:click={newChat}>+ 新对话</button>
  </div>

  <!-- Messages area -->
  <div class="messages" bind:this={messagesEl}>
    {#if $messages.length === 0}
      <div class="empty-hint">
        <p>👋 你好！我是 NextAgent Doc Assistant。</p>
        <p>请描述你需要编写的文档，例如：</p>
        <ul>
          <li>帮我编写用户认证模块的需求规格文档</li>
          <li>更新 API 文档中的登录接口说明</li>
        </ul>
      </div>
    {/if}

    {#each $messages as msg (msg.ts + msg.role)}
      <div class="msg msg-{msg.role}">
        <div class="bubble">
          {#if msg.statusSteps?.length}
            <div class="status-steps" class:no-border={!msg.content && !msg.docs?.length}>
              {#each msg.statusSteps as step, i}
                {@const isDone = i < msg.statusSteps.length - 1 || !!msg.content}
                <div class="status-step">
                  <span class="step-icon">{isDone ? '✓' : '⏳'}</span>
                  <span class="step-text">{step}</span>
                </div>
              {/each}
            </div>
          {/if}
          {#if msg.content}
            <span class="content">{msg.content}</span>
          {/if}
          <!-- Generated documents -->
          {#if msg.docs?.length}
            <div class="docs-list">
              {#each msg.docs as doc}
                <div class="doc-item">
                  <span class="doc-icon">📄</span>
                  <span class="doc-path">{doc.file_path}</span>
                  <span class="doc-ver">v{doc.version}</span>
                  <button class="copy-btn" on:click={() => copyPath(doc.file_path)}>复制路径</button>
                </div>
              {/each}
            </div>
          {/if}
          <!-- Meta bar: skill selection + token usage (shown after done) -->
          {#if msg.role === 'assistant' && (msg.metaSkillName || msg.metaUsage)}
            <div class="meta-bar">
              <div class="meta-tags">
                {#if msg.metaSkillName}
                  <span class="skill-badge">🎯 {msg.metaSkillName}</span>
                {/if}
                {#if msg.metaUsage}
                  <span class="token-badge">📊 {msg.metaUsage.total_tokens} tokens</span>
                {/if}
              </div>
              {#if msg.metaSkillReason}
                <span class="skill-reason">{msg.metaSkillReason}</span>
              {/if}
            </div>
          {/if}
          <!-- Save draft button (non-blocking, independent of input) -->
          {#if msg.hasDraft && msg.role === 'assistant'}
            {@const saveState = draftSaveState[msg.ts] || 'idle'}
            {@const saveResult = draftSaveResult[msg.ts]}
            <div class="draft-actions">
              {#if saveState === 'saved' && saveResult}
                <span class="draft-saved">✓ 已保存 v{saveResult.version}</span>
                <span class="draft-path">{saveResult.file_path}</span>
              {:else}
                <button
                  class="btn-save-draft"
                  class:saving={saveState === 'saving'}
                  disabled={saveState === 'saving' || saveState === 'saved'}
                  on:click={() => saveDraft(msg)}
                >
                  {saveState === 'saving' ? '保存中...' : '💾 保存为正式版本'}
                </button>
              {/if}
            </div>
          {/if}
        </div>
      </div>
    {/each}

    {#if $streaming && !$messages.at(-1)?.content}
      <div class="msg msg-assistant"><div class="bubble typing">●●●</div></div>
    {/if}
  </div>

  <!-- Input area -->
  <div class="input-area">
    <textarea
      bind:value={inputText}
      on:keydown={onKeydown}
      placeholder="输入你的文档需求…（Enter 发送，Shift+Enter 换行）"
      rows="3"
      disabled={$streaming}
    />
    {#if $streaming}
      <button class="btn-stop send-btn" on:click={stopStreaming}>停止</button>
    {:else}
      <button class="btn-primary send-btn" on:click={sendMessage} disabled={!inputText.trim()}>发送</button>
    {/if}
  </div>
</div>

<style>
.chat-root { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.chat-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border); }
.title { font-weight: 600; font-size: 15px; }

.messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }

.empty-hint { color: var(--text-muted); text-align: center; margin-top: 60px; line-height: 2; }
.empty-hint ul { text-align: left; display: inline-block; margin-top: 8px; }

.msg { display: flex; }
.msg-user { justify-content: flex-end; }
.msg-assistant { justify-content: flex-start; }

.bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-user .bubble { background: var(--accent); color: #fff; border-bottom-right-radius: 3px; }
.msg-assistant .bubble { background: var(--surface2); color: var(--text); border-bottom-left-radius: 3px; }

.status-steps { margin-bottom: 8px; display: flex; flex-direction: column; gap: 3px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
.status-steps.no-border { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.status-step { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); }
.step-icon { font-size: 11px; min-width: 14px; }
.step-text { font-style: italic; }
.typing { letter-spacing: 4px; color: var(--text-muted); }

.docs-list { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
.doc-item {
  display: flex; align-items: center; gap: 8px;
  background: var(--surface); padding: 6px 10px; border-radius: 6px;
  font-size: 12px;
}
.doc-path { flex: 1; color: var(--text-muted); font-family: monospace; font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-ver { color: var(--success); }
.copy-btn { background: none; border: 1px solid var(--border); border-radius: 4px; padding: 2px 8px; font-size: 11px; color: var(--text-muted); cursor: pointer; }
.copy-btn:hover { background: var(--surface2); }

.input-area { display: flex; gap: 10px; padding: 12px 16px; border-top: 1px solid var(--border); align-items: flex-end; }
.input-area textarea { flex: 1; resize: none; }
.send-btn { height: 60px; min-width: 80px; }
.btn-stop { height: 60px; min-width: 80px; background: var(--surface2); color: var(--text); border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-stop:hover { background: #fee2e2; color: #dc2626; border-color: #fca5a5; }

.meta-bar {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.meta-tags { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.skill-badge {
  display: inline-block;
  background: rgba(99, 102, 241, 0.12);
  color: #6366f1;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 500;
}
.token-badge {
  display: inline-block;
  background: var(--surface);
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
}
.skill-reason {
  font-size: 11px;
  color: var(--text-muted);
  font-style: italic;
  line-height: 1.5;
}

.draft-actions {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.btn-save-draft {
  background: none;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 12px;
  font-size: 12px;
  color: var(--text);
  cursor: pointer;
  transition: background 0.15s;
}
.btn-save-draft:hover:not(:disabled) { background: var(--surface2); }
.btn-save-draft.saving { opacity: 0.6; cursor: default; }
.btn-save-draft:disabled { cursor: default; }
.draft-saved { font-size: 12px; color: var(--success); font-weight: 500; }
.draft-path { font-size: 11px; color: var(--text-muted); font-family: monospace; }</style>
