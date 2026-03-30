<script>
  import { obsStore } from '$lib/stores.js';

  $: panelOpen = $obsStore.panelOpen;
  $: events = $obsStore.events;
  $: items = buildItems(events);

  // Pre-process events into structured items.
  // After a tool_call, all subsequent thinking + detail events are nested
  // as children of that tool_call, until the next tool_call starts.
  function buildItems(evts) {
    const result = [];
    let currentTool = null;

    for (const e of evts) {
      if (e.type === 'thinking') {
        if (currentTool) {
          currentTool.children.push({ kind: 'inner_thinking', event: e });
        } else {
          result.push({ kind: 'thinking', event: e });
        }
      } else if (e.type === 'status' && e.extra?.sub === 'tool_call') {
        currentTool = { kind: 'tool_call', event: e, children: [] };
        result.push(currentTool);
      } else if (e.type === 'status' && e.extra?.sub === 'detail') {
        if (currentTool) {
          currentTool.children.push({ kind: 'detail', event: e });
        }
      } else if (e.type === 'status') {
        // Generic status (e.g. draft loaded) — top-level, resets tool context
        currentTool = null;
        result.push({ kind: 'status', event: e });
      } else if (e.type === 'question') {
        currentTool = null;
        result.push({ kind: 'question', event: e });
      } else if (e.type === 'subagent_start') {
        currentTool = null;
        result.push({ kind: 'subagent_start', event: e });
      } else if (e.type === 'done') {
        currentTool = null;
        result.push({ kind: 'done', event: e });
      }
    }
    return result;
  }

  const KIND_COLOR = {
    thinking:       'var(--primary)',
    tool_call:      '#8b5cf6',
    status:         'var(--text-muted)',
    question:       'var(--warning)',
    skill:          '#8b5cf6',
    subagent_start: '#0ea5e9',
    done:           'var(--success)',
  };
  const KIND_ICON = {
    thinking:       'lightbulb',
    tool_call:      'settings',
    status:         'check_circle',
    question:       'help',
    skill:          'extension',
    subagent_start: 'smart_toy',
    done:           'task_alt',
  };
  const KIND_LABEL = {
    thinking:       '思考',
    tool_call:      '工具调用',
    status:         '状态',
    question:       '提问',
    skill:          '技能调用',
    subagent_start: '子 Agent',
    done:           '完成',
  };

  function formatTokens(usage) {
    if (!usage) return null;
    const total = usage.total_tokens || (usage.prompt_tokens + usage.completion_tokens);
    return `${usage.prompt_tokens ?? '–'} + ${usage.completion_tokens ?? '–'} = ${total}`;
  }
</script>

<!-- Chevron toggle -->
<button
  class="panel-toggle"
  class:open={panelOpen}
  on:click={obsStore.togglePanel}
  title={panelOpen ? '折叠面板' : '展开过程明细'}
>
  <span class="material-symbols-outlined" style="font-size:16px;">
    {panelOpen ? 'chevron_right' : 'chevron_left'}
  </span>
</button>

<!-- Panel -->
<div class="obs-panel" class:open={panelOpen}>
  <div class="panel-header">
    <span class="material-symbols-outlined" style="font-size:15px;color:var(--primary);font-variation-settings:'FILL' 1,'wght' 500;">analytics</span>
    <span class="panel-title">过程明细</span>
    <button class="close-btn" on:click={obsStore.closePanel} title="关闭">
      <span class="material-symbols-outlined" style="font-size:16px;">close</span>
    </button>
  </div>

  <div class="panel-content">
    {#if items.length === 0}
      <div class="empty-hint">
        <span class="material-symbols-outlined" style="font-size:32px;color:var(--text-muted);opacity:0.4;font-variation-settings:'FILL' 0,'wght' 300;">query_stats</span>
        <p>等待 Agent 运行…</p>
      </div>
    {:else}
      <div class="timeline">
        {#each items as item}
          {@const color = KIND_COLOR[item.kind] ?? 'var(--text-muted)'}
          {@const icon  = KIND_ICON[item.kind]  ?? 'circle'}
          {@const label = KIND_LABEL[item.kind] ?? item.kind}

          <div class="tl-item">
            <div class="tl-line" style="--c: {color}"></div>
            <div class="tl-dot"  style="background: {color}"></div>

            <div class="tl-head">
              <span class="tl-label" style="color: {color}">
                <span class="material-symbols-outlined" style="font-size:11px;font-variation-settings:'FILL' 1,'wght' 500;">{icon}</span>
                {label}
              </span>
              {#if item.event?.extra?.tool}
                <span class="tool-tag">{item.event.extra.tool}</span>
              {/if}
            </div>

            <!-- Content by kind -->
            {#if item.kind === 'thinking'}
              <div class="card thinking-card">
                <div class="thinking-text">{item.event.content}</div>
              </div>

            {:else if item.kind === 'tool_call'}
              <div class="card tool-card">{item.event.content}</div>
              <!-- Nested children: detail results + inner thinking -->
              {#if item.children?.length}
                <div class="children">
                  {#each item.children as child}
                    {#if child.kind === 'detail'}
                      <div class="child-detail">
                        <span class="child-arrow">↳</span>
                        <span class="material-symbols-outlined" style="font-size:11px;color:var(--primary);opacity:0.6;font-variation-settings:'FILL' 1,'wght' 400;">database</span>
                        <span class="child-text">{child.event.content}</span>
                      </div>
                    {:else if child.kind === 'inner_thinking'}
                      <div class="child-thinking">
                        <span class="child-arrow">↳</span>
                        <span class="material-symbols-outlined" style="font-size:11px;color:var(--primary);opacity:0.4;font-variation-settings:'FILL' 0,'wght' 400;">lightbulb</span>
                        <span class="child-text thinking-inner">{child.event.content}</span>
                      </div>
                    {/if}
                  {/each}
                </div>
              {/if}

            {:else if item.kind === 'status'}
              <div class="card status-card">
                <span class="material-symbols-outlined" style="font-size:12px;color:var(--success);font-variation-settings:'FILL' 1,'wght' 400;">check_circle</span>
                {item.event.content}
              </div>

            {:else if item.kind === 'question'}
              <div class="card question-card">
                <span class="material-symbols-outlined" style="font-size:13px;color:var(--warning);font-variation-settings:'FILL' 1,'wght' 500;">help</span>
                <span>{item.event.content}</span>
              </div>

            {:else if item.kind === 'skill'}
              <div class="card skill-card">
                <span class="skill-name">{item.event.content}</span>
                {#if item.event.extra?.reason}
                  <span class="skill-reason">{item.event.extra.reason}</span>
                {/if}
              </div>

            {:else if item.kind === 'subagent_start'}
              <div class="card subagent-card">
                <span class="material-symbols-outlined" style="font-size:13px;color:#0ea5e9;font-variation-settings:'FILL' 1,'wght' 500;">smart_toy</span>
                <span class="subagent-name">{item.event.content}</span>
                {#if item.event.extra?.skill_id}
                  <span class="subagent-skill-tag">{item.event.extra.skill_id}</span>
                {/if}
              </div>

            {:else if item.kind === 'done'}
              <div class="card done-card">
                {#if item.event.extra?.skill_name}
                  <div class="done-row">
                    <span class="material-symbols-outlined" style="font-size:12px;color:#8b5cf6;font-variation-settings:'FILL' 1,'wght' 500;">extension</span>
                    <span>{item.event.extra.skill_name}</span>
                  </div>
                {/if}
                {#if item.event.extra?.usage}
                  {@const tokens = formatTokens(item.event.extra.usage)}
                  {#if tokens}
                    <div class="done-row">
                      <span class="material-symbols-outlined" style="font-size:12px;color:var(--success);">bar_chart</span>
                      <span>{tokens} tokens</span>
                    </div>
                  {/if}
                {/if}
              </div>
            {/if}

          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
/* ── Toggle ── */
.panel-toggle {
  flex-shrink: 0;
  width: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--base);
  border: none;
  border-left: 1.5px solid var(--dividers);
  color: var(--text-muted);
  cursor: pointer;
  padding: 0;
  transition: color 0.15s, background 0.15s;
  align-self: stretch;
}
.panel-toggle:hover { color: var(--primary); background: var(--primary-surface); }
.panel-toggle.open { border-left-color: transparent; border-right: 1.5px solid var(--dividers); }

/* ── Panel ── */
.obs-panel {
  flex: 0 0 0%;
  width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--lowest);
  transition: flex-basis 0.3s cubic-bezier(0.4, 0, 0.2, 1), width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.obs-panel.open { flex: 0 0 40%; width: auto; }

/* ── Header ── */
.panel-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  background: var(--base);
  border-bottom: 1.5px solid var(--dividers);
  white-space: nowrap;
}
.panel-title { flex: 1; font-size: 13px; font-weight: 600; color: var(--text); }
.close-btn {
  background: none; border: none; color: var(--text-muted);
  cursor: pointer; padding: 2px; border-radius: var(--radius-sm);
  display: flex; align-items: center; line-height: 1;
}
.close-btn:hover { color: var(--text); background: var(--high); }

/* ── Content ── */
.panel-content { flex: 1; overflow-y: auto; padding: 16px 14px; overflow-x: hidden; }

.empty-hint {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding-top: 40px; color: var(--text-muted); font-size: 12px; text-align: center;
}

/* ── Timeline ── */
.timeline { display: flex; flex-direction: column; }

.tl-item {
  position: relative;
  padding-left: 22px;
  padding-bottom: 16px;
}

.tl-line {
  position: absolute;
  left: 6px; top: 12px; bottom: -16px;
  width: 2px;
  background: linear-gradient(to bottom, var(--c), transparent);
  border-radius: 1px;
}
.tl-dot {
  position: absolute;
  left: 2px; top: 5px;
  width: 10px; height: 10px;
  border-radius: 50%;
}

.tl-head {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 6px;
}
.tl-label {
  font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.07em;
  display: flex; align-items: center; gap: 5px;
}
.tool-tag {
  font-size: 9px; font-family: monospace;
  color: var(--text-muted); opacity: 0.5;
  background: var(--high); padding: 2px 6px;
  border-radius: 2px; flex-shrink: 0;
}

/* ── Cards ── */
.card {
  background: var(--base); border-radius: var(--radius);
  padding: 9px 12px; font-size: 12px; color: var(--text);
  line-height: 1.6; white-space: normal; word-break: break-word;
}
.thinking-card { background: var(--primary-surface); color: var(--text-muted); font-style: italic; padding: 0; }
.thinking-text { max-height: 200px; overflow-y: auto; padding: 9px 12px; white-space: pre-line; line-height: 1.5; }
.tool-card { font-weight: 500; }
.status-card { display: flex; align-items: flex-start; gap: 6px; color: var(--text-muted); }
.question-card { display: flex; align-items: flex-start; gap: 8px; background: rgba(245,158,11,0.08); border-left: 3px solid var(--warning); }
.skill-card { display: flex; flex-direction: column; gap: 3px; }
.skill-name { font-weight: 600; color: #8b5cf6; }
.skill-reason { font-size: 11px; color: var(--text-muted); font-style: italic; }
.subagent-card { display: flex; align-items: center; gap: 6px; background: rgba(14,165,233,0.08); border-left: 3px solid #0ea5e9; }
.subagent-name { font-weight: 600; color: #0ea5e9; flex: 1; }
.subagent-skill-tag { font-size: 10px; color: #0ea5e9; opacity: 0.7; background: rgba(14,165,233,0.12); border-radius: 4px; padding: 1px 5px; font-family: monospace; white-space: nowrap; }
.done-card { background: rgba(34,197,94,0.08); border-left: 3px solid var(--success); display: flex; flex-direction: column; gap: 4px; }
.done-row { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--text-muted); }

/* ── Children (nested under tool_call) ── */
.children { margin-top: 6px; display: flex; flex-direction: column; gap: 3px; }

.child-detail, .child-thinking {
  display: flex; align-items: flex-start; gap: 5px;
  margin-left: 8px; padding: 4px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
}
.child-detail { background: var(--high); color: var(--text); }
.child-thinking { background: var(--primary-surface); color: var(--text-muted); font-style: italic; }

.child-arrow { color: var(--primary); opacity: 0.4; font-size: 10px; flex-shrink: 0; line-height: 1.6; }
.child-text { line-height: 1.5; white-space: pre-line; word-break: break-word; }
.thinking-inner { opacity: 0.8; }
</style>
