<script>
  import { onMount } from 'svelte';
  import { llmConfigList, notify } from '$lib/stores.js';
  import { llmConfigs } from '$lib/api.js';
  import Icon from '$lib/components/Icon.svelte';

  let showForm = false;
  let editingId = null;
  let testing = null;

  let form = emptyForm();
  function emptyForm() {
    return { name: '', provider: 'deepseek', model_name: '', api_base: '', api_key: '', temperature: 0.7, max_tokens: 4096, top_p: 0.9, reasoning_mode: 'default', is_default: false };
  }

  onMount(async () => { await refresh(); });

  async function refresh() {
    const res = await llmConfigs.list();
    llmConfigList.set(res);
  }

  function openAdd() { form = emptyForm(); editingId = null; showForm = true; }
  function openEdit(cfg) { form = { ...cfg, api_key: '' }; editingId = cfg.id; showForm = true; }

  async function save() {
    try {
      if (editingId) {
        const body = { ...form };
        if (!body.api_key) delete body.api_key;
        await llmConfigs.update(editingId, body);
        notify('success', '配置已更新');
      } else {
        await llmConfigs.create(form);
        notify('success', '配置已添加');
      }
      showForm = false;
      await refresh();
    } catch (e) { notify('error', e.message); }
  }

  async function remove(id) {
    if (!confirm('确定删除该配置？')) return;
    await llmConfigs.delete(id);
    notify('success', '配置已删除');
    await refresh();
  }

  async function setDefault(id) {
    await llmConfigs.setDefault(id);
    notify('success', '已设置为默认模型');
    await refresh();
  }

  async function testConn(id) {
    testing = id;
    try {
      const res = await llmConfigs.test(id);
      notify(res.success ? 'success' : 'error', res.success ? '连接成功' : `连接失败：${res.error}`);
    } catch (e) { notify('error', e.message); }
    finally { testing = null; }
  }

  const providerLabels = { deepseek: 'DeepSeek', qwen: 'QWen', ollama: '本地模型（vLLM/Ollama）' };
  const reasoningLabels = {
    default: '默认推理',
    thinking: '思考模式',
    'non-thinking': '非思考模式',
  };
  const providerPresets = {
    deepseek: {
      modelName: 'deepseek-chat',
      apiBase: 'https://api.deepseek.com'
    },
    qwen: {
      modelName: 'qwen-max',
      apiBase: 'https://dashscope.aliyuncs.com'
    },
    ollama: {
      modelName: 'qwen2.5-coder:14b-instruct-q5_K_S',
      apiBase: 'http://192.168.5.162:11434'
    }
  };
</script>

<div class="page">
  <div class="page-header">
    <div>
      <h2>LLM 模型配置</h2>
      <p class="page-subtitle">管理 AI 模型连接配置</p>
    </div>
    <button class="btn-primary" on:click={openAdd}>
      <Icon name="add" style="font-size:16px;vertical-align:middle;" />
      添加配置
    </button>
  </div>

  <div class="hint-bar">
    <Icon name="info" style="font-size:16px;color:var(--warning);" />
    <span>API 令牌仅存储在本地服务器，不会发送至外部服务。请定期更新令牌。</span>
  </div>

  {#if $llmConfigList.length === 0}
    <div class="empty">
      <Icon name="settings" style="font-size:36px;color:var(--dividers);" />
      <p>暂无配置</p>
      <p class="empty-hint">请添加 DeepSeek、QWen 或 Ollama 模型</p>
    </div>
  {:else}
    <div class="config-list">
      {#each $llmConfigList as cfg}
        <div class="config-card {cfg.is_default ? 'is-default' : ''}">
          <div class="config-top">
            <div class="config-left">
              <div class="config-icon">
                <Icon name="smart_toy" style="font-size:20px;color:var(--primary);" />
              </div>
              <div>
                <div class="config-name-row">
                  <span class="config-name">{cfg.name}</span>
                  {#if cfg.is_default}<span class="badge-success">默认</span>{/if}
                  {#if !cfg.is_active}<span class="badge-warning">已禁用</span>{/if}
                </div>
                <div class="config-detail">
                  <span class="provider-tag">{providerLabels[cfg.provider] || cfg.provider}</span>
                  <span class="meta-sep">·</span>
                  <span>{cfg.model_name}</span>
                  <span class="meta-sep">·</span>
                  <span class="key-display">{cfg.api_key_masked}</span>
                  <span class="meta-sep">·</span>
                  <span>温度 {cfg.temperature}</span>
                  <span class="meta-sep">·</span>
                  <span>{reasoningLabels[cfg.reasoning_mode] || '默认推理'}</span>
                </div>
              </div>
            </div>
            <div class="config-actions">
              <button class="btn-ghost sm" on:click={() => testConn(cfg.id)} disabled={testing === cfg.id}>
                <Icon name={testing === cfg.id ? 'sync' : 'wifi'} spin={testing === cfg.id} style="font-size:14px;" />
                {testing === cfg.id ? '测试中…' : '测试'}
              </button>
              {#if !cfg.is_default}
                <button class="btn-ghost sm" on:click={() => setDefault(cfg.id)}>
                  <Icon name="star" style="font-size:14px;" />
                  设为默认
                </button>
              {/if}
              <button class="btn-ghost sm" on:click={() => openEdit(cfg)}>
                <Icon name="edit" style="font-size:14px;" />
              </button>
              <button class="btn-danger sm" on:click={() => remove(cfg.id)}>
                <Icon name="delete" style="font-size:14px;" />
              </button>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

{#if showForm}
  <div
    class="overlay"
    role="button"
    tabindex="0"
    on:click|self={() => showForm = false}
    on:keydown={(e) => {
      if ((e.key === 'Enter' || e.key === ' ') && e.currentTarget === e.target) {
        showForm = false;
      }
    }}
  >
    <div class="modal">
      <div class="modal-header">
        <h3>{editingId ? '编辑配置' : '添加 LLM 配置'}</h3>
        <button class="btn-ghost" on:click={() => showForm = false}>
          <Icon name="close" style="font-size:16px;" />
        </button>
      </div>
      <div class="form-group">
        <label for="llm-config-name">配置名称 <span class="required">*</span></label>
        <input id="llm-config-name" bind:value={form.name} placeholder="如：生产环境 DeepSeek" />
      </div>
      <div class="form-group">
        <label for="llm-config-provider">模型提供商 <span class="required">*</span></label>
        <select id="llm-config-provider" bind:value={form.provider}>
          <option value="deepseek">DeepSeek</option>
          <option value="qwen">QWen（通义千问）</option>
          <option value="ollama">本地模型（vLLM/Ollama）</option>
        </select>
      </div>
      <div class="form-group">
        <label for="llm-config-model">模型名称 <span class="required">*</span></label>
        <input id="llm-config-model" bind:value={form.model_name} placeholder={providerPresets[form.provider]?.modelName || ''} />
      </div>
      <div class="form-group">
        <label for="llm-config-api-base">API 地址 <span class="required">*</span></label>
        <input id="llm-config-api-base" bind:value={form.api_base} placeholder={providerPresets[form.provider]?.apiBase || ''} />
        {#if form.provider === 'ollama'}
          <div class="field-hint">可直接填写服务根地址，系统会自动补全 OpenAI 兼容的 <code>/v1</code> 路径。</div>
        {/if}
      </div>
      <div class="form-group">
        <label for="llm-config-api-key">
          API 令牌
          {#if !editingId && form.provider !== 'ollama'}<span class="required">*</span>{/if}
          {#if editingId}<span class="label-hint">（留空保持不变）</span>{/if}
        </label>
        <input id="llm-config-api-key" type="password" bind:value={form.api_key} placeholder={form.provider === 'ollama' ? '本地服务通常可留空' : 'sk-...'} />
        {#if form.provider === 'ollama'}
          <div class="field-hint">使用本地 vLLM 或 Ollama 的 OpenAI 兼容接口时，通常不需要填写 API 令牌。</div>
        {/if}
      </div>
      <details class="advanced-wrap">
        <summary>高级参数</summary>
        <div class="form-row">
          <div class="form-group"><label for="llm-config-temperature">温度 (0–2)</label><input id="llm-config-temperature" type="number" min="0" max="2" step="0.1" bind:value={form.temperature} /></div>
          <div class="form-group">
            <label for="llm-config-max-tokens">最大输出令牌数</label>
            <input id="llm-config-max-tokens" type="number" min="256" max="32768" bind:value={form.max_tokens} />
            <div class="field-hint">限制单次回复最多生成多少 tokens，不等于模型的上下文窗口大小。</div>
          </div>
          <div class="form-group"><label for="llm-config-top-p">Top-P (0–1)</label><input id="llm-config-top-p" type="number" min="0" max="1" step="0.05" bind:value={form.top_p} /></div>
        </div>
        <div class="form-group">
          <label for="llm-config-reasoning-mode">推理模式</label>
          <select id="llm-config-reasoning-mode" bind:value={form.reasoning_mode}>
            <option value="default">默认</option>
            <option value="thinking">思考模式</option>
            <option value="non-thinking">非思考模式</option>
          </select>
          <div class="field-hint">推荐将 Qwen3.5 的编排模型设为“非思考模式”，减少工具调用时输出额外思考文本。</div>
        </div>
      </details>
      <label class="checkbox-label">
        <input type="checkbox" bind:checked={form.is_default} />
        <span>设为默认模型</span>
      </label>
      <div class="modal-actions">
        <button class="btn-ghost" on:click={() => showForm = false}>取消</button>
        <button class="btn-primary" on:click={save}>保存</button>
      </div>
    </div>
  </div>
{/if}

<style>
.page { padding: 28px 32px; max-width: 820px; }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
h2 { font-family: var(--font-headline); font-size: 20px; font-weight: 700; color: var(--text); }
.page-subtitle { font-size: 13px; color: var(--text-muted); margin-top: 3px; }

.hint-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(245,158,11,0.08);
  border-radius: var(--radius);
  padding: 10px 14px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 20px;
}

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

.config-list { display: flex; flex-direction: column; gap: 10px; }

.config-card {
  background: var(--lowest);
  border-radius: var(--radius-lg);
  padding: 16px 20px;
  box-shadow: var(--shadow-soft);
  transition: box-shadow 0.2s;
}
.config-card.is-default { outline: 2px solid var(--primary); outline-offset: -1px; }
.config-card:hover { box-shadow: var(--shadow-float); }

.config-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.config-left { display: flex; align-items: center; gap: 14px; flex: 1; min-width: 0; }
.config-icon {
  width: 40px;
  height: 40px;
  background: var(--primary-surface);
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.config-name-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.config-name { font-weight: 700; font-size: 14px; }
.config-detail { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); flex-wrap: wrap; }
.provider-tag {
  background: var(--primary-surface);
  color: var(--primary);
  border-radius: var(--radius-sm);
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 600;
}
.meta-sep { color: var(--dividers); }
.key-display { font-family: monospace; }
.config-actions { display: flex; gap: 6px; flex-shrink: 0; }
.sm { display: inline-flex; align-items: center; gap: 4px; padding: 6px 10px; font-size: 12px; }

/* Modal */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(15,23,42,0.4);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: var(--lowest);
  border-radius: var(--radius-xl);
  padding: 28px;
  width: 440px;
  max-width: 95vw;
  box-shadow: var(--shadow-float);
}
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.modal-header h3 { font-family: var(--font-headline); font-size: 16px; font-weight: 700; color: var(--text); }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 5px; }
.field-hint { margin-top: 6px; font-size: 12px; color: var(--text-muted); }
.required { color: var(--danger); }
.label-hint { font-weight: 400; color: var(--text-muted); }
.form-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.advanced-wrap { margin-bottom: 14px; }
.advanced-wrap summary { cursor: pointer; color: var(--text-muted); font-size: 12px; padding: 6px 0; font-weight: 600; }
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  margin-bottom: 20px;
  cursor: pointer;
  color: var(--text);
}
.checkbox-label input { width: auto; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
