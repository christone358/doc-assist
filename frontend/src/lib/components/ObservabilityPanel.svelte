<script>
  import { obsStore } from '$lib/stores.js';

  let expanded = {};

  $: panelOpen = $obsStore.panelOpen;
  $: nodes = $obsStore.nodes || [];
  $: events = $obsStore.events || [];
  $: nodeTree = buildNodeTree(nodes);
  $: legacyItems = nodeTree.length === 0 ? buildLegacyItems(events) : [];

  const TYPE_META = {
    llm_thought:  { label: 'LLM 思考', icon: 'lightbulb', color: 'var(--primary)' },
    tool_call:    { label: '工具调用', icon: 'build', color: '#2563eb' },
    skill_call:   { label: 'Skill 调用', icon: 'extension', color: '#7c3aed' },
    user_question:{ label: '用户提问', icon: 'help', color: 'var(--warning)' },
    system_state: { label: '系统状态', icon: 'task_alt', color: 'var(--success)' },
  };

  const STATUS_LABEL = {
    running: '运行中',
    waiting: '等待中',
    completed: '已完成',
    failed: '失败',
  };

  function toggleExpand(key) {
    expanded = { ...expanded, [key]: !expanded[key] };
  }

  function byCreatedOrder(a, b) {
    const orderA = a.created_order ?? Number.MAX_SAFE_INTEGER;
    const orderB = b.created_order ?? Number.MAX_SAFE_INTEGER;
    if (orderA !== orderB) return orderA - orderB;
    return String(a.created_at || '').localeCompare(String(b.created_at || ''));
  }

  function buildNodeTree(inputNodes) {
    if (!Array.isArray(inputNodes) || inputNodes.length === 0) return [];

    const clones = inputNodes
      .slice()
      .sort(byCreatedOrder)
      .map((node) => ({ ...node, children: [] }));

    const map = new Map(clones.map((node) => [node.node_id, node]));
    const roots = [];

    for (const node of clones) {
      if (node.parent_node_id && map.has(node.parent_node_id)) {
        map.get(node.parent_node_id).children.push(node);
      } else {
        roots.push(node);
      }
    }

    for (const node of clones) {
      node.children.sort(byCreatedOrder);
    }
    return roots;
  }

  function buildLegacyItems(evts) {
    return (evts || []).map((event, index) => ({
      id: `${event.type}-${index}`,
      label: legacyLabel(event),
      content: event.content || event.extra?.display_text || '过程事件',
    }));
  }

  function legacyLabel(event) {
    if (event.type === 'thinking') return 'LLM 思考';
    if (event.type === 'question') return '用户提问';
    if (event.type === 'skill') return 'Skill 调用';
    if (event.type === 'execution_event') return '执行事件';
    if (event.type === 'done') return '系统状态';
    return '过程事件';
  }

  function actorLabel(actor) {
    if (actor === 'subagent') return '子 Agent';
    if (actor === 'orchestrator') return '主 Agent';
    if (actor === 'runtime') return '运行时';
    if (actor === 'user') return '用户';
    return '';
  }

  function nodeMeta(node) {
    return TYPE_META[node.node_type] || TYPE_META.system_state;
  }

  function statusLabel(status) {
    return STATUS_LABEL[status] || status || '';
  }

  function nodeTitle(node) {
    if (node.node_type === 'tool_call') {
      return node.tool_name || node.title || '工具调用';
    }
    if (node.node_type === 'skill_call') {
      return node.skill_name || node.skill_id || node.title || 'Skill 调用';
    }
    return node.title || node.node_type;
  }

  function nodeSummary(node) {
    return node.output_preview || node.detail_text || node.reason || '';
  }

  function nodeDetail(node) {
    return node.output_detail || node.detail_text || '';
  }

  function hasDetail(node) {
    return node.output_detail !== undefined;
  }

  function toolSourceLabel(source) {
    if (source === 'mcp') return 'MCP';
    if (source === 'internal') return '内部';
    if (source === 'builtin') return '内置';
    return '';
  }

  function toolHeader(node) {
    const title = node.tool_name || node.title || '工具调用';
    const status = statusLabel(node.status);
    return status ? `${title} · ${status}` : title;
  }
</script>

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

<div class="obs-panel" class:open={panelOpen}>
  <div class="panel-header">
    <span class="material-symbols-outlined" style="font-size:15px;color:var(--primary);font-variation-settings:'FILL' 1,'wght' 500;">analytics</span>
    <span class="panel-title">过程明细</span>
    <button class="close-btn" on:click={obsStore.closePanel} title="关闭">
      <span class="material-symbols-outlined" style="font-size:16px;">close</span>
    </button>
  </div>

  <div class="panel-content">
    {#if nodeTree.length === 0 && legacyItems.length === 0}
      <div class="empty-hint">
        <span class="material-symbols-outlined" style="font-size:32px;color:var(--text-muted);opacity:0.4;font-variation-settings:'FILL' 0,'wght' 300;">query_stats</span>
        <p>等待 Agent 运行…</p>
      </div>
    {:else if nodeTree.length > 0}
      <div class="node-list">
        {#each nodeTree as node}
          {@const meta = nodeMeta(node)}
          <div class="node-card" style={`--node-color: ${meta.color};`}>
            <div class="node-head">
              <div class="node-kind" style={`color:${meta.color};`}>
                <span class="material-symbols-outlined" style="font-size:13px;font-variation-settings:'FILL' 1,'wght' 500;">{meta.icon}</span>
                <span>{meta.label}</span>
              </div>
              {#if actorLabel(node.actor)}
                <span class="node-tag">{actorLabel(node.actor)}</span>
              {/if}
              {#if node.node_type === 'tool_call' && toolSourceLabel(node.tool_source)}
                <span class="node-tag">{toolSourceLabel(node.tool_source)}</span>
              {/if}
              {#if statusLabel(node.status)}
                <span class="status-pill" class:failed={node.status === 'failed'}>{statusLabel(node.status)}</span>
              {/if}
            </div>

            <div class="node-title">
              {node.node_type === 'tool_call' ? toolHeader(node) : nodeTitle(node)}
            </div>

            {#if node.node_type === 'llm_thought'}
              <div class="text-block">{nodeDetail(node)}</div>
            {/if}

            {#if node.node_type === 'tool_call'}
              <div class="kv-block">
                <div class="kv-label">输入</div>
                <div class="kv-value pre-wrap">{node.display_input || '无'}</div>
              </div>
              <div class="kv-block">
                <div class="kv-label">输出摘要</div>
                <div class="kv-value pre-wrap">{node.output_preview || '无'}</div>
              </div>
              <details class="detail-box" open={expanded[node.node_id]} on:toggle={() => toggleExpand(node.node_id)}>
                <summary>详细信息</summary>
                <div class="detail-content pre-wrap">{node.output_detail || '无详细输出'}</div>
              </details>
            {/if}

            {#if node.node_type === 'skill_call'}
              {#if node.reason}
                <div class="kv-block">
                  <div class="kv-label">交接摘要</div>
                  <div class="kv-value pre-wrap">{node.reason}</div>
                </div>
              {/if}
              {#if node.output_preview}
                <div class="kv-block">
                  <div class="kv-label">执行结果</div>
                  <div class="kv-value pre-wrap">{node.output_preview}</div>
                </div>
              {/if}
              {#if node.children.length}
                <div class="child-list">
                  {#each node.children as child}
                    {@const childMeta = nodeMeta(child)}
                    <div class="child-card" style={`--node-color: ${childMeta.color};`}>
                      <div class="node-head">
                        <div class="node-kind" style={`color:${childMeta.color};`}>
                          <span class="material-symbols-outlined" style="font-size:12px;font-variation-settings:'FILL' 1,'wght' 500;">{childMeta.icon}</span>
                          <span>{childMeta.label}</span>
                        </div>
                        {#if statusLabel(child.status)}
                          <span class="status-pill" class:failed={child.status === 'failed'}>{statusLabel(child.status)}</span>
                        {/if}
                      </div>
                      <div class="node-title">{child.node_type === 'tool_call' ? toolHeader(child) : nodeTitle(child)}</div>
                      {#if child.node_type === 'tool_call'}
                        <div class="kv-block">
                          <div class="kv-label">输入</div>
                          <div class="kv-value pre-wrap">{child.display_input || '无'}</div>
                        </div>
                        <div class="kv-block">
                          <div class="kv-label">输出摘要</div>
                          <div class="kv-value pre-wrap">{child.output_preview || '无'}</div>
                        </div>
                        <details class="detail-box">
                          <summary>详细信息</summary>
                          <div class="detail-content pre-wrap">{child.output_detail || '无详细输出'}</div>
                        </details>
                      {:else}
                        <div class="text-block">{nodeSummary(child) || nodeDetail(child) || '无详细信息'}</div>
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}
            {/if}

            {#if node.node_type === 'user_question' || node.node_type === 'system_state'}
              <div class="text-block">{nodeSummary(node) || nodeDetail(node) || '无详细信息'}</div>
            {/if}

            {#if node.is_truncated}
              <div class="truncate-hint">部分内容已截断</div>
            {/if}
          </div>
        {/each}
      </div>
    {:else}
      <div class="legacy-list">
        {#each legacyItems as item}
          <div class="legacy-card">
            <div class="legacy-label">{item.label}</div>
            <div class="legacy-content">{item.content}</div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
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
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  line-height: 1;
}
.close-btn:hover { color: var(--text); background: var(--high); }

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 14px;
  overflow-x: hidden;
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding-top: 40px;
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}

.node-list,
.legacy-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.node-card,
.legacy-card,
.child-card {
  background: var(--base);
  border-left: 3px solid var(--node-color, var(--dividers));
  border-radius: var(--radius);
  padding: 10px 12px;
}

.child-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.node-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.node-kind {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.node-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 8px;
  word-break: break-word;
}

.node-tag {
  font-size: 10px;
  font-family: monospace;
  color: var(--text-muted);
  background: var(--high);
  padding: 2px 6px;
  border-radius: 999px;
}

.status-pill {
  font-size: 10px;
  color: var(--success);
  background: rgba(34,197,94,0.12);
  padding: 2px 6px;
  border-radius: 999px;
}

.status-pill.failed {
  color: var(--danger, #dc2626);
  background: rgba(220,38,38,0.12);
}

.kv-block {
  margin-top: 8px;
}

.kv-label,
.legacy-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.kv-value,
.legacy-content,
.text-block,
.detail-content {
  font-size: 12px;
  color: var(--text);
  line-height: 1.6;
  word-break: break-word;
}

.pre-wrap {
  white-space: pre-wrap;
}

.detail-box {
  margin-top: 8px;
  background: var(--lowest);
  border-radius: var(--radius-sm);
  padding: 6px 8px;
}

.detail-box summary {
  cursor: pointer;
  font-size: 11px;
  color: var(--text-muted);
}

.truncate-hint {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
}
</style>
