<script>
  import { onMount, onDestroy, tick } from 'svelte';
  import { marked } from 'marked';
  import { activeConvId, messages, streaming, wsConn, notify, triggerConvRefresh, obsStore } from '$lib/stores.js';
  import { conversations, openChatSocket } from '$lib/api.js';
  import ObservabilityPanel from '$lib/components/ObservabilityPanel.svelte';

  // Configure marked: break on newlines, no pedantic mode
  marked.setOptions({ breaks: true, gfm: true });

  let inputText = '';
  let messagesEl;
  let ws = null;
  let _pingTimer = null;

  // 保活：streaming 期间每 20s 发一次 ping，防止网络层空闲超时切断连接
  const unsubStreaming = streaming.subscribe(active => {
    clearInterval(_pingTimer);
    if (active) {
      _pingTimer = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ ping: true }));
        }
      }, 20000);
    }
  });

  // React to activeConvId changes (sidebar click)
  const unsubConvId = activeConvId.subscribe(id => {
    if (id) switchConversation(id);
    else { messages.set([]); ws?.close(); obsStore.clearEvents(); }
  });

  onMount(() => {
    if ($activeConvId) switchConversation($activeConvId);
  });

  onDestroy(() => {
    unsubConvId();
    unsubStreaming();
    clearInterval(_pingTimer);
    ws?.close();
    streaming.set(false);
  });

  let _currentConvId = null;

  async function switchConversation(id) {
    if (id === _currentConvId) return;

    // 若正在进行中（streaming），提示用户切换将丢失本轮内容
    if ($streaming) {
      const ok = window.confirm('当前对话正在进行中，切换将丢失本轮未完成的内容。是否继续切换？');
      if (!ok) {
        // 撤回 activeConvId，保持当前对话
        activeConvId.set(_currentConvId);
        return;
      }
    }
    _currentConvId = id;
    streaming.set(false);
    currentAssistantMsg = null;
    obsStore.clearEvents();
    ws?.close();
    const conv = await conversations.get(id);
    if (_currentConvId !== id) return;
    const msgs = (conv.rounds || []).flatMap(r => [
      { role: 'user', content: r.user_input, ts: r.timestamp },
      {
        role: 'assistant',
        content: r.agent_response,
        docs: r.documents_generated,
        ts: r.timestamp,
        metaSkillId: r.skill_invoked || null,
        metaSkillName: r.skill_invoked || null,
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
    _currentConvId = res.conversation_id;
    activeConvId.set(res.conversation_id);
    messages.set([]);
    ws?.close();
    ws = openSocket(res.conversation_id);
    wsConn.set(ws);
    triggerConvRefresh();
    return res.conversation_id;
  }

  let currentAssistantMsg = null;

  function openSocket(convId) {
    const sock = openChatSocket(convId, handleWSMessage);
    sock.addEventListener('close', () => {
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
      // Feed observability store (all sub-types)
      if (data.type === 'skill_start') {
        obsStore.addEvent({ type: 'skill', content: data.content || `Skill: ${data.skill_id}`, extra: { reason: data.reason } });
      } else {
        obsStore.addEvent({ type: 'status', content: data.content, extra: { sub: data.sub, tool: data.tool } });
      }
      // Left bubble statusSteps: only high-level steps, skip detail sub-events
      if (data.sub === 'detail') return;
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
    } else if (data.type === 'subagent_start') {
      obsStore.addEvent({ type: 'subagent_start', content: data.skill_name || data.skill_id, extra: { skill_id: data.skill_id, skill_name: data.skill_name } });
    } else if (data.type === 'question') {
      obsStore.addEvent({ type: 'question', content: data.content });
      // Finalize the current process bubble (thinking/status), start a fresh one for the question
      currentAssistantMsg = { role: 'assistant', content: data.content, docs: [], statusSteps: [], ts: new Date().toISOString() };
      messages.update(m => [...m, currentAssistantMsg]);
      scrollToBottom();
    } else if (data.type === 'thinking') {
      obsStore.addEvent({ type: 'thinking', content: data.content });
      if (!currentAssistantMsg) {
        currentAssistantMsg = { role: 'assistant', content: '', docs: [], statusSteps: [], thinking: '', thinkingOpen: false, ts: new Date().toISOString() };
        messages.update(m => [...m, currentAssistantMsg]);
      }
      currentAssistantMsg.thinking = (currentAssistantMsg.thinking || '') + data.content;
      messages.update(m => m);
      scrollToBottom();
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
      obsStore.addEvent({ type: 'done', content: 'done', extra: { skill_name: data.skill_name, usage: data.usage } });
      if (currentAssistantMsg) {
        currentAssistantMsg.metaSkillId = data.skill_id || null;
        currentAssistantMsg.metaSkillName = data.skill_name || null;
        currentAssistantMsg.metaSkillReason = data.skill_reason || null;
        currentAssistantMsg.metaUsage = data.usage || null;
        currentAssistantMsg.hasDraft = data.has_draft === true;
        if (currentAssistantMsg.thinking) currentAssistantMsg.thinkingOpen = false;
        messages.update(m => m);
      }
      streaming.set(false);
      currentAssistantMsg = null;
      // Auto-name: trigger on first round if name is still default
      tryAutoName();
    } else if (data.type === 'error') {
      obsStore.addEvent({ type: 'status', content: data.content || '发生错误', extra: { sub: 'error' } });
      if (!currentAssistantMsg) {
        currentAssistantMsg = {
          role: 'assistant',
          content: data.content || '发生错误',
          docs: [],
          statusSteps: [],
          ts: new Date().toISOString(),
          isError: true
        };
        messages.update(m => [...m, currentAssistantMsg]);
      } else {
        currentAssistantMsg.content = data.content || '发生错误';
        currentAssistantMsg.isError = true;
        if (currentAssistantMsg.thinking) currentAssistantMsg.thinkingOpen = false;
        messages.update(m => m);
      }
      streaming.set(false);
      notify('error', data.content || '发生错误');
      scrollToBottom();
      currentAssistantMsg = null;
    }
  }

  function stopStreaming() {
    streaming.set(false);
    if (currentAssistantMsg) {
      if (!currentAssistantMsg.content) currentAssistantMsg.content = '[已中断]';
      messages.update(m => m);
      currentAssistantMsg = null;
    }
    ws?.close();
  }

  async function sendMessage() {
    const text = inputText.trim();
    if (!text) return;

    obsStore.clearEvents();

    if (!$activeConvId) {
      await createConversation();
    }

    inputText = '';

    if ($streaming) {
      messages.update(m => [...m, { role: 'user', content: text, ts: new Date().toISOString() }]);
      currentAssistantMsg = null;  // 清空，后续 Agent 响应作为新的一轮对话
      await scrollToBottom();
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ message: text }));
      }
      return;
    }

    streaming.set(true);
    currentAssistantMsg = null;

    messages.update(m => [...m, { role: 'user', content: text, ts: new Date().toISOString() }]);
    await scrollToBottom();

    if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
      ws = openSocket($activeConvId);
      wsConn.set(ws);
    }

    const doSend = () => ws.send(JSON.stringify({ message: text }));

    if (ws.readyState === WebSocket.OPEN) {
      doSend();
    } else {
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

  function copyPath(path) {
    navigator.clipboard?.writeText(path);
    notify('success', '路径已复制');
  }

  // Auto-name: refresh sidebar after first round so server-generated title appears
  async function tryAutoName() {
    const convId = $activeConvId;
    if (!convId) return;
    // Only trigger on the first round (messages: 1 user + 1 assistant = 2 entries)
    if ($messages.length !== 2) return;
    // Small delay to let the server finish naming before we refresh
    await new Promise(r => setTimeout(r, 1500));
    triggerConvRefresh();
  }

  let draftSaveState = {};
  let draftSaveResult = {};

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
  <div class="chat-pane">
    <!-- Header -->
    <div class="chat-header">
      <span class="title">对话</span>
    </div>

  <!-- Messages area -->
  <div class="messages" bind:this={messagesEl}>
    {#if $messages.length === 0}
      <div class="empty-hint">
        <div class="empty-icon">
          <span class="material-symbols-outlined" style="font-size:40px;color:var(--primary);font-variation-settings:'FILL' 0,'wght' 300;">auto_awesome</span>
        </div>
        <p class="empty-title">你好！我是 NextAgent Doc Assistant</p>
        <p class="empty-subtitle">请描述你需要编写的文档，例如：</p>
        <ul>
          <li>帮我编写用户认证模块的需求规格文档</li>
          <li>更新 API 文档中的登录接口说明</li>
        </ul>
      </div>
    {/if}

    {#each $messages as msg, msgIdx (msg.ts + msg.role)}
      {@const isLastMsg = msgIdx === $messages.length - 1}      <div class="msg msg-{msg.role}">
        {#if msg.role === 'assistant'}
          <div class="avatar">
            <span class="material-symbols-outlined" style="font-size:16px;color:var(--primary);font-variation-settings:'FILL' 1,'wght' 500;">auto_awesome</span>
          </div>
        {/if}
        <div class="bubble" class:error-bubble={msg.isError}>
          {#if msg.thinking}
            <div class="thinking-block">
              <button class="thinking-toggle" on:click={() => { msg.thinkingOpen = !msg.thinkingOpen; messages.update(m => m); }}>
                <span class="material-symbols-outlined" style="font-size:14px;">{msg.thinkingOpen ? 'expand_less' : 'expand_more'}</span>
                <span>思考过程</span>
                {#if isLastMsg}
                <button class="obs-open-btn" on:click|stopPropagation={obsStore.togglePanel} title="展开/收起过程明细">
                  <span class="material-symbols-outlined" style="font-size:13px;color:var(--primary);">analytics</span>
                </button>
                {/if}
              </button>
              {#if msg.thinkingOpen}
                <div class="thinking-body">{msg.thinking}</div>
              {/if}
            </div>
          {/if}
          {#if msg.statusSteps?.length}
            <div class="status-steps" class:no-border={!msg.content && !msg.docs?.length}>
              {#each msg.statusSteps as step, i}
                {@const isDone = i < msg.statusSteps.length - 1 || !!msg.content}
                <div class="status-step">
                  <span class="material-symbols-outlined step-icon" style="font-size:13px;font-variation-settings:'FILL' 1,'wght' 400;">{isDone ? 'check_circle' : 'pending'}</span>
                  <span class="step-text">{step}</span>
                </div>
              {/each}
            </div>
          {/if}
          {#if msg.content}
            {#if msg.role === 'assistant'}
              <div class="content markdown">{@html marked.parse(msg.content)}</div>
            {:else}
              <span class="content">{msg.content}</span>
            {/if}
          {/if}
          {#if msg.docs?.length}
            <div class="docs-list">
              {#each msg.docs as doc}
                <div class="doc-item">
                  <span class="material-symbols-outlined" style="font-size:15px;color:var(--primary);font-variation-settings:'FILL' 1,'wght' 400;">description</span>
                  <span class="doc-path">{doc.file_path}</span>
                  <span class="doc-ver">v{doc.version}</span>
                  <button class="copy-btn" on:click={() => copyPath(doc.file_path)}>复制路径</button>
                </div>
              {/each}
            </div>
          {/if}
          {#if msg.role === 'assistant' && (msg.metaSkillName || msg.metaUsage)}
            <div class="meta-bar">
              <div class="meta-tags">
                {#if msg.metaSkillName}
                  <span class="skill-badge">
                    <span class="material-symbols-outlined" style="font-size:12px;font-variation-settings:'FILL' 1,'wght' 500;">extension</span>
                    {msg.metaSkillName}
                  </span>
                {/if}
                {#if msg.metaUsage}
                  <span class="token-badge">
                    <span class="material-symbols-outlined" style="font-size:12px;">bar_chart</span>
                    {msg.metaUsage.total_tokens} tokens
                  </span>
                {/if}
              </div>
              {#if msg.metaSkillReason}
                <span class="skill-reason">{msg.metaSkillReason}</span>
              {/if}
            </div>
          {/if}
          {#if msg.hasDraft && msg.role === 'assistant'}
            {@const saveState = draftSaveState[msg.ts] || 'idle'}
            {@const saveResult = draftSaveResult[msg.ts]}
            <div class="draft-actions">
              {#if saveState === 'saved' && saveResult}
                <span class="draft-saved">
                  <span class="material-symbols-outlined" style="font-size:14px;font-variation-settings:'FILL' 1,'wght' 500;">check_circle</span>
                  已保存 v{saveResult.version}
                </span>
                <span class="draft-path">{saveResult.file_path}</span>
              {:else}
                <button
                  class="btn-save-draft"
                  class:saving={saveState === 'saving'}
                  disabled={saveState === 'saving' || saveState === 'saved'}
                  on:click={() => saveDraft(msg)}
                >
                  <span class="material-symbols-outlined" style="font-size:14px;">save</span>
                  {saveState === 'saving' ? '保存中...' : '保存为正式版本'}
                </button>
              {/if}
            </div>
          {/if}
        </div>
      </div>
    {/each}

    {#if $streaming && !$messages.at(-1)?.content}
      <div class="msg msg-assistant">
        <div class="avatar">
          <span class="material-symbols-outlined" style="font-size:16px;color:var(--primary);font-variation-settings:'FILL' 1,'wght' 500;">auto_awesome</span>
        </div>
        <div class="bubble typing">
          <span></span><span></span><span></span>
        </div>
      </div>
    {/if}
  </div>

  <!-- Input area -->
  <div class="input-area">
    <div class="input-pill">
      <textarea
        bind:value={inputText}
        on:keydown={onKeydown}
        placeholder="输入你的文档需求…（Enter 发送，Shift+Enter 换行）"
        rows="3"
      />
      <div class="input-actions">
        {#if $streaming}
          <button class="btn-stop-inline" on:click={stopStreaming} title="停止">
            <span class="material-symbols-outlined" style="font-size:18px;">stop_circle</span>
          </button>
        {/if}
        <button
          class="btn-send"
          on:click={sendMessage}
          disabled={!inputText.trim()}
          title="发送 (Enter)"
        >
          <span class="material-symbols-outlined" style="font-size:18px;font-variation-settings:'FILL' 1,'wght' 600;">send</span>
        </button>
      </div>
    </div>
  </div>
  </div><!-- end .chat-pane -->
  <ObservabilityPanel />
</div>

<style>
.chat-root { display: flex; flex-direction: row; height: 100%; overflow: hidden; background: var(--lowest); }
.chat-pane { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; }

/* ── Header ── */
.chat-header {
  display: flex;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1.5px solid var(--dividers);
}

/* ── Messages ── */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  margin-top: 60px;
  gap: 8px;
}
.empty-icon { margin-bottom: 8px; }
.empty-title {
  font-family: var(--font-headline);
  font-weight: 700;
  font-size: 18px;
  color: var(--text);
}
.empty-subtitle { color: var(--text-muted); font-size: 14px; }
.empty-hint ul {
  text-align: left;
  display: inline-block;
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 13px;
  list-style: none;
}
.empty-hint ul li::before { content: '→ '; color: var(--primary); }
.empty-hint ul li { margin-bottom: 4px; }

/* ── Message rows ── */
.msg { display: flex; align-items: flex-start; gap: 10px; }
.msg-user { justify-content: flex-end; }
.msg-assistant { justify-content: flex-start; }

.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--primary-surface);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.bubble {
  max-width: 72%;
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  line-height: 1.6;
  word-break: break-word;
}
.msg-user .bubble {
  background: var(--primary);
  color: #fff;
  border-bottom-right-radius: var(--radius-sm);
  box-shadow: 0 4px 12px rgba(99,102,241,0.25);
}
.msg-assistant .bubble {
  background: var(--base);
  color: var(--text);
  border-bottom-left-radius: var(--radius-sm);
}
.bubble.error-bubble {
  background: color-mix(in srgb, var(--danger) 8%, var(--base));
  border: 1px solid color-mix(in srgb, var(--danger) 28%, transparent);
}
.bubble.error-bubble .content,
.bubble.error-bubble .content.markdown {
  color: var(--danger);
}

/* Plain text */
.content { white-space: pre-wrap; }

/* Markdown */
.content.markdown { line-height: 1.75; }
.content.markdown :global(h1) { font-family: var(--font-headline); font-size: 1.25em; font-weight: 700; margin: 0.9em 0 0.4em; color: var(--text); }
.content.markdown :global(h2) { font-family: var(--font-headline); font-size: 1.1em; font-weight: 700; margin: 0.75em 0 0.35em; }
.content.markdown :global(h3) { font-size: 1.0em; font-weight: 600; margin: 0.6em 0 0.25em; }
.content.markdown :global(p)  { margin: 0.4em 0; }
.content.markdown :global(ul), .content.markdown :global(ol) { padding-left: 1.4em; margin: 0.3em 0; }
.content.markdown :global(li) { margin: 0.2em 0; }
.content.markdown :global(code) { background: var(--high); border-radius: var(--radius-sm); padding: 1px 5px; font-family: monospace; font-size: 0.88em; color: var(--primary); }
.content.markdown :global(pre) { background: var(--high); border-radius: var(--radius); padding: 12px; overflow-x: auto; margin: 0.5em 0; }
.content.markdown :global(pre code) { background: none; padding: 0; color: var(--text); }
.content.markdown :global(blockquote) { border-left: 3px solid var(--dividers); padding-left: 12px; color: var(--text-muted); margin: 0.4em 0; }
.content.markdown :global(table) { border-collapse: collapse; width: 100%; font-size: 0.9em; margin: 0.5em 0; }
.content.markdown :global(th), .content.markdown :global(td) { border: 1px solid var(--dividers); padding: 6px 10px; }
.content.markdown :global(th) { background: var(--high); font-weight: 600; }
.content.markdown :global(strong) { font-weight: 600; }
.content.markdown :global(em) { font-style: italic; }

/* Thinking */
.thinking-block {
  margin-bottom: 10px;
  background: var(--primary-surface);
  border-radius: var(--radius);
  overflow: hidden;
  font-size: 12px;
}
.thinking-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
  text-align: left;
}
.thinking-toggle span:nth-child(2) { flex: 1; }
.obs-open-btn {
  background: none;
  border: none;
  padding: 2px;
  cursor: pointer;
  display: flex;
  align-items: center;
  border-radius: var(--radius-sm);
  opacity: 0.7;
}
.obs-open-btn:hover { opacity: 1; background: rgba(99,102,241,0.1); }
.thinking-toggle:hover { opacity: 0.8; }
.thinking-body {
  padding: 8px 12px 10px;
  white-space: pre-line;
  color: var(--text-muted);
  font-style: italic;
  line-height: 1.6;
  max-height: 280px;
  overflow-y: auto;
}

/* Status steps */
.status-steps {
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-bottom: 1.5px solid var(--dividers);
  padding-bottom: 10px;
}
.status-steps.no-border { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.status-step { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); }
.step-icon { color: var(--success); }

/* Typing indicator */
.typing {
  display: flex;
  gap: 5px;
  align-items: center;
  padding: 14px 16px;
}
.typing span {
  width: 7px;
  height: 7px;
  background: var(--primary);
  border-radius: 50%;
  animation: bounce 1.2s infinite;
  opacity: 0.6;
}
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.6; }
  40% { transform: translateY(-5px); opacity: 1; }
}

/* Docs list */
.docs-list { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
.doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--primary-surface);
  padding: 7px 12px;
  border-radius: var(--radius);
  font-size: 12px;
}
.doc-path { flex: 1; color: var(--text-muted); font-family: monospace; font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-ver { color: var(--primary); font-weight: 600; font-size: 11px; }
.copy-btn {
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  font-size: 11px;
  color: var(--text-muted);
  cursor: pointer;
  background: rgba(99,102,241,0.08);
}
.copy-btn:hover { background: rgba(99,102,241,0.16); color: var(--primary); }

/* Meta bar */
.meta-bar {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1.5px solid var(--dividers);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.meta-tags { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.skill-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--primary-surface);
  color: var(--primary);
  border-radius: var(--radius-sm);
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 600;
}
.token-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--high);
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  padding: 3px 8px;
  font-size: 12px;
}
.skill-reason { font-size: 11px; color: var(--text-muted); font-style: italic; line-height: 1.5; }

/* Draft actions */
.draft-actions {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1.5px solid var(--dividers);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.btn-save-draft {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: var(--primary-surface);
  border: none;
  border-radius: var(--radius);
  padding: 6px 14px;
  font-size: 12px;
  color: var(--primary);
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-save-draft:hover:not(:disabled) { opacity: 0.8; }
.btn-save-draft.saving { opacity: 0.6; }
.draft-saved { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--success); font-weight: 600; }
.draft-path { font-size: 11px; color: var(--text-muted); font-family: monospace; }

/* Question prompt */
.question-prompt {
  margin-top: 10px;
  padding: 10px 14px;
  background: rgba(245,158,11,0.08);
  border-left: 3px solid var(--warning);
  border-radius: var(--radius-sm);
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.question-text { font-size: 13px; color: var(--text); line-height: 1.6; white-space: pre-wrap; }

/* ── Input area — pill shape ── */
.input-area {
  padding: 16px 24px 20px;
  background: var(--lowest);
}
.input-pill {
  display: flex;
  align-items: flex-end;
  gap: 0;
  background: var(--base);
  border-radius: var(--radius-xl);
  padding: 12px 14px 10px;
  box-shadow: 0 4px 20px rgba(99,102,241,0.10), 0 1px 4px rgba(0,0,0,0.05);
  border: 1.5px solid transparent;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.input-pill:focus-within {
  border-color: rgba(99,102,241,0.25);
  box-shadow: 0 6px 24px rgba(99,102,241,0.15), 0 1px 4px rgba(0,0,0,0.05);
}
.input-pill textarea {
  flex: 1;
  resize: none;
  border: none;
  background: transparent;
  padding: 0 8px 0 4px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text);
  font-family: var(--font-body);
  min-height: 48px;
}
.input-pill textarea:focus { border: none; box-shadow: none; }

.input-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  padding-bottom: 2px;
}

.btn-send {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  box-shadow: 0 3px 10px rgba(99,102,241,0.35);
  transition: opacity 0.15s, box-shadow 0.15s;
}
.btn-send:hover:not(:disabled) { opacity: 0.9; box-shadow: 0 5px 14px rgba(99,102,241,0.45); }
.btn-send:disabled { background: var(--dividers); color: var(--text-muted); box-shadow: none; }

.btn-stop-inline {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--high);
  color: var(--danger);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background 0.15s;
}
.btn-stop-inline:hover { background: rgba(239,68,68,0.1); }
</style>
