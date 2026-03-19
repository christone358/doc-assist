<script>
  import { onMount } from 'svelte';
  import { llmConfigList, notify } from '$lib/stores.js';
  import { llmConfigs } from '$lib/api.js';

  let showForm = false;
  let editingId = null;
  let testing = null;

  let form = emptyForm();
  function emptyForm() {
    return { name: '', provider: 'deepseek', model_name: '', api_base: '', api_key: '', temperature: 0.7, max_tokens: 4096, top_p: 0.9, is_default: false };
  }

  onMount(async () => {
    await refresh();
  });

  async function refresh() {
    const res = await llmConfigs.list();
    llmConfigList.set(res);
  }

  function openAdd() { form = emptyForm(); editingId = null; showForm = true; }

  function openEdit(cfg) {
    form = { ...cfg, api_key: '' }; // don't pre-fill key
    editingId = cfg.id;
    showForm = true;
  }

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
    } catch (e) {
      notify('error', e.message);
    }
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
      notify(res.success ? 'success' : 'error', res.success ? '连接成功 ✓' : `连接失败：${res.error}`);
    } catch (e) {
      notify('error', e.message);
    } finally {
      testing = null;
    }
  }
</script>

<div class="page">
  <div class="page-header">
    <h2>LLM 模型配置</h2>
    <button class="btn-primary" on:click={openAdd}>+ 添加配置</button>
  </div>

  <p class="hint">⚠️ API 令牌仅存储在本地服务器，不会发送至外部服务。请定期更新令牌。</p>

  {#if $llmConfigList.length === 0}
    <div class="empty">暂无配置。请添加 DeepSeek 或 QWen 模型。</div>
  {:else}
    <div class="config-list">
      {#each $llmConfigList as cfg}
        <div class="config-card {cfg.is_default ? 'is-default' : ''}">
          <div class="config-top">
            <div>
              <span class="config-name">{cfg.name}</span>
              {#if cfg.is_default}<span class="badge-success">默认</span>{/if}
              {#if !cfg.is_active}<span class="badge-warning">已禁用</span>{/if}
            </div>
            <div class="config-actions">
              <button class="btn-ghost" on:click={() => testConn(cfg.id)} disabled={testing === cfg.id}>
                {testing === cfg.id ? '测试中…' : '测试连接'}
              </button>
              {#if !cfg.is_default}
                <button class="btn-ghost" on:click={() => setDefault(cfg.id)}>设为默认</button>
              {/if}
              <button class="btn-ghost" on:click={() => openEdit(cfg)}>编辑</button>
              <button class="btn-danger" on:click={() => remove(cfg.id)}>删除</button>
            </div>
          </div>
          <div class="config-detail">
            <span class="tag">{cfg.provider}</span>
            <span>{cfg.model_name}</span>
            <span class="sep">·</span>
            <span class="key-display">{cfg.api_key_masked}</span>
            <span class="sep">·</span>
            <span>温度 {cfg.temperature}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- Add / Edit form modal -->
{#if showForm}
  <div class="overlay" on:click|self={() => showForm = false}>
    <div class="modal">
      <h3>{editingId ? '编辑配置' : '添加 LLM 配置'}</h3>
      <div class="form-group">
        <label>配置名称 *</label>
        <input bind:value={form.name} placeholder="如：生产环境 DeepSeek" />
      </div>
      <div class="form-group">
        <label>模型提供商 *</label>
        <select bind:value={form.provider}>
          <option value="deepseek">DeepSeek</option>
          <option value="qwen">QWen（通义千问）</option>
        </select>
      </div>
      <div class="form-group">
        <label>模型名称 *</label>
        <input bind:value={form.model_name} placeholder={form.provider === 'deepseek' ? 'deepseek-chat' : 'qwen-max'} />
      </div>
      <div class="form-group">
        <label>API 地址 *</label>
        <input bind:value={form.api_base} placeholder={form.provider === 'deepseek' ? 'https://api.deepseek.com' : 'https://dashscope.aliyuncs.com'} />
      </div>
      <div class="form-group">
        <label>API 令牌 {editingId ? '（留空保持不变）' : '*'}</label>
        <input type="password" bind:value={form.api_key} placeholder="sk-..." />
      </div>
      <details>
        <summary>高级参数</summary>
        <div class="advanced">
          <div class="form-row">
            <div class="form-group"><label>温度 (0-2)</label><input type="number" min="0" max="2" step="0.1" bind:value={form.temperature} /></div>
            <div class="form-group"><label>最大令牌数</label><input type="number" min="256" max="32768" bind:value={form.max_tokens} /></div>
            <div class="form-group"><label>Top-P (0-1)</label><input type="number" min="0" max="1" step="0.05" bind:value={form.top_p} /></div>
          </div>
        </div>
      </details>
      <label class="checkbox-label">
        <input type="checkbox" bind:checked={form.is_default} /> 设为默认模型
      </label>
      <div class="modal-actions">
        <button class="btn-ghost" on:click={() => showForm = false}>取消</button>
        <button class="btn-primary" on:click={save}>保存</button>
      </div>
    </div>
  </div>
{/if}

<style>
.page { padding: 20px; max-width: 800px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
h2 { font-size: 18px; font-weight: 600; }
.hint { color: var(--text-muted); font-size: 12px; margin-bottom: 16px; background: var(--surface2); padding: 8px 12px; border-radius: 6px; }
.empty { color: var(--text-muted); text-align: center; margin-top: 40px; }

.config-list { display: flex; flex-direction: column; gap: 10px; }
.config-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px; }
.config-card.is-default { border-color: var(--accent); }
.config-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; gap: 8px; }
.config-name { font-weight: 500; margin-right: 8px; }
.config-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.config-detail { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-muted); }
.sep { color: var(--border); }
.key-display { font-family: monospace; }

.overlay { position: fixed; inset: 0; background: rgba(0,0,0,.6); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 24px; width: 420px; max-width: 95vw; }
.modal h3 { font-size: 16px; font-weight: 600; margin-bottom: 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
.form-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
details summary { cursor: pointer; color: var(--text-muted); font-size: 12px; margin-bottom: 8px; }
.advanced { margin-top: 8px; }
.checkbox-label { display: flex; align-items: center; gap: 8px; font-size: 13px; margin-bottom: 16px; cursor: pointer; }
.checkbox-label input { width: auto; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
</style>
