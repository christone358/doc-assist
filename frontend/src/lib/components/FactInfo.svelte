<script>
  import { onMount } from 'svelte';
  import { factInfo } from '$lib/api.js';

  let items = [];
  let selected = null;
  let selectedDetail = null;
  let keyword = '';
  let system = '';
  let systems = [];
  let groupedItems = [];
  let groupedFunctionPoints = [];
  let isRefreshing = false;
  let refreshMessage = '';

  function buildGroups(sourceItems) {
    const systemMap = new Map();

    for (const item of sourceItems) {
      const systemName = item.system || '未标注系统';
      const subsystemName = item.subsystem || '';

      if (!systemMap.has(systemName)) {
        systemMap.set(systemName, {
          name: systemName,
          directModules: [],
          subsystemMap: new Map(),
        });
      }

      const systemGroup = systemMap.get(systemName);
      if (!subsystemName) {
        systemGroup.directModules.push(item);
        continue;
      }

      if (!systemGroup.subsystemMap.has(subsystemName)) {
        systemGroup.subsystemMap.set(subsystemName, {
          name: subsystemName,
          modules: [],
        });
      }
      systemGroup.subsystemMap.get(subsystemName).modules.push(item);
    }

    return [...systemMap.values()].map((systemGroup) => ({
      name: systemGroup.name,
      directModules: systemGroup.directModules,
      subsystems: [...systemGroup.subsystemMap.values()],
    }));
  }

  onMount(() => load());

  async function load(preferredSelectedId = selected?.id) {
    const params = {};
    if (keyword) params.keyword = keyword;
    if (system) params.system = system;
    const res = await factInfo.list(params);
    items = res.items || [];
    systems = [...new Set(items.map((item) => item.system).filter(Boolean))];
    groupedItems = buildGroups(items);

    const matchedSelected = preferredSelectedId
      ? items.find((item) => item.id === preferredSelectedId)
      : null;

    if (selected && !matchedSelected) {
      selected = null;
      selectedDetail = null;
    }

    if (matchedSelected) {
      await select(matchedSelected);
      return;
    }

    if (!selected && items.length > 0) {
      await select(items[0]);
    }
  }

  async function select(item) {
    selected = item;
    selectedDetail = await factInfo.get(item.id);
    groupedFunctionPoints = groupFunctionPoints(selectedDetail?.function_points || []);
  }

  function groupFunctionPoints(points) {
    const groups = new Map();
    const directKey = '__direct__';

    for (const point of points) {
      const submodule = point['子模块'] || '';
      const key = submodule || directKey;
      if (!groups.has(key)) {
        groups.set(key, {
          name: submodule,
          items: [],
        });
      }
      groups.get(key).items.push(point);
    }

    return [...groups.values()];
  }

  async function refreshFacts() {
    isRefreshing = true;
    refreshMessage = '';
    const currentSelectedId = selected?.id;

    try {
      const result = await factInfo.refresh();
      await load(currentSelectedId);
      refreshMessage = result?.message || '项目事实信息已更新';
    } catch (error) {
      refreshMessage = error?.message || '更新失败';
    } finally {
      isRefreshing = false;
    }
  }
</script>

<div class="page">
  <div class="page-header">
    <div>
      <h2>项目事实信息</h2>
      <p class="page-subtitle">模块档案是唯一人工维护源，右侧展示模块详情与关联信息。</p>
    </div>
    <button class="refresh-button" on:click={refreshFacts} disabled={isRefreshing}>
      {isRefreshing ? '更新中…' : '更新'}
    </button>
  </div>

  {#if refreshMessage}
    <div class="refresh-message">{refreshMessage}</div>
  {/if}

  <div class="toolbar">
    <div class="search-wrap">
      <span class="material-symbols-outlined" style="font-size:16px;color:var(--text-muted);">search</span>
      <input bind:value={keyword} placeholder="搜索模块、用例、功能点或 API…" on:input={load} />
    </div>

    <div class="filter-wrap">
      <span class="material-symbols-outlined" style="font-size:16px;color:var(--text-muted);">apartment</span>
      <select bind:value={system} on:change={load}>
        <option value="">全部系统</option>
        {#each systems as systemName}
          <option value={systemName}>{systemName}</option>
        {/each}
      </select>
    </div>
  </div>

  {#if items.length === 0}
    <div class="empty">
      <span class="material-symbols-outlined" style="font-size:36px;color:var(--dividers);font-variation-settings:'FILL' 0,'wght' 300;">auto_stories</span>
      <p>暂无模块档案</p>
      <p class="empty-hint">请在 <code>project-facts/modules/</code> 下维护模块档案，或先执行迁移脚本。</p>
    </div>
  {:else}
    <div class="content-shell">
      <div class="items-panel">
        <div class="items-list">
          {#each groupedItems as systemGroup}
            <div class="system-group">
              <div class="group-title">{systemGroup.name}</div>

              {#if systemGroup.directModules.length}
                <div class="group-section">
                  {#each systemGroup.directModules as item}
                    <button class="item-row {selected?.id === item.id ? 'active' : ''}" on:click={() => select(item)}>
                      <div class="item-main">
                        <div class="item-title-row">
                          <span class="item-name">{item.name}</span>
                        </div>
                        <div class="item-meta">
                          <span>用例 {item.counts?.usecases || 0}</span>
                          <span>子模块 {item.counts?.submodules || 0}</span>
                          <span>功能点 {item.counts?.function_points || 0}</span>
                          <span>API {item.counts?.apis || 0}</span>
                          <span>页面 {item.counts?.prototype_pages || 0}</span>
                        </div>
                        {#if item.description}
                          <div class="item-desc">{item.description}</div>
                        {/if}
                      </div>
                      <span class="material-symbols-outlined chevron" style="font-size:16px;">chevron_right</span>
                    </button>
                  {/each}
                </div>
              {/if}

              {#each systemGroup.subsystems as subsystemGroup}
                <div class="subsystem-group">
                  <div class="subsystem-title">{subsystemGroup.name}</div>
                  <div class="group-section">
                    {#each subsystemGroup.modules as item}
                      <button class="item-row {selected?.id === item.id ? 'active' : ''}" on:click={() => select(item)}>
                        <div class="item-main">
                          <div class="item-title-row">
                            <span class="item-name">{item.name}</span>
                          </div>
                          <div class="item-meta">
                            <span>用例 {item.counts?.usecases || 0}</span>
                            <span>子模块 {item.counts?.submodules || 0}</span>
                            <span>功能点 {item.counts?.function_points || 0}</span>
                            <span>API {item.counts?.apis || 0}</span>
                            <span>页面 {item.counts?.prototype_pages || 0}</span>
                          </div>
                          {#if item.description}
                            <div class="item-desc">{item.description}</div>
                          {/if}
                        </div>
                        <span class="material-symbols-outlined chevron" style="font-size:16px;">chevron_right</span>
                      </button>
                    {/each}
                  </div>
                </div>
              {/each}
            </div>
          {/each}
        </div>
      </div>

      <div class="detail-panel">
        {#if selectedDetail}
          <div class="detail-header">
            <div>
              <div class="d-name">{selectedDetail.name}</div>
              <div class="detail-meta">
                <span>{selectedDetail.system || '未标注系统'}</span>
                {#if selectedDetail.subsystem}<span>{selectedDetail.subsystem}</span>{/if}
                <span>用例 {selectedDetail.usecases?.length || 0}</span>
                <span>子模块 {selectedDetail.submodules?.length || 0}</span>
                {#if selectedDetail.path}<span>{selectedDetail.path}</span>{/if}
              </div>
            </div>
          </div>

          <div class="detail-content">
            <section>
              <h3>功能描述</h3>
              <p>{selectedDetail.description || '待补充'}</p>
            </section>

            <section>
              <h3>用例信息</h3>
              {#if selectedDetail.usecases?.length}
                <table>
                  <thead>
                    <tr><th>用例</th><th>描述</th><th>参与角色</th></tr>
                  </thead>
                  <tbody>
                    {#each selectedDetail.usecases as usecase}
                      <tr>
                        <td>{usecase['用例']}</td>
                        <td>{usecase['描述']}</td>
                        <td>{usecase['参与角色']}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              {:else}
                <p class="placeholder">待补充</p>
              {/if}
            </section>

            <section>
              <h3>子模块与功能点</h3>
              {#if groupedFunctionPoints.length}
                <div class="submodule-sections">
                  {#each groupedFunctionPoints as group}
                    <div class="submodule-section">
                      <div class="submodule-section-title">
                        {group.name || '未归类功能点'}
                      </div>
                      <table>
                        <thead>
                          <tr><th>功能点</th><th>描述</th><th>状态</th></tr>
                        </thead>
                        <tbody>
                          {#each group.items as item}
                            <tr>
                              <td>{item['功能点']}</td>
                              <td>{item['描述']}</td>
                              <td>{item['状态']}</td>
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    </div>
                  {/each}
                </div>
              {:else}
                <p class="placeholder">待补充</p>
              {/if}
            </section>

            <section>
              <h3>API 清单</h3>
              {#if selectedDetail.apis?.length}
                <table>
                  <thead>
                    <tr><th>API 名称</th><th>说明</th><th>路径</th><th>方法</th></tr>
                  </thead>
                  <tbody>
                    {#each selectedDetail.apis as api}
                      <tr>
                        <td>{api['API 名称']}</td>
                        <td>{api['说明']}</td>
                        <td>{api['路径']}</td>
                        <td>{api['方法']}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              {:else}
                <p class="placeholder">待补充</p>
              {/if}
            </section>

            <section>
              <h3>页面 / 原型</h3>
              {#if selectedDetail.prototype_pages?.length}
                <ul>
                  {#each selectedDetail.prototype_pages as page}
                    <li>
                      <span>{page.name}</span>
                      {#if page.path}
                        <code>{page.path}</code>
                      {/if}
                    </li>
                  {/each}
                </ul>
              {:else}
                <p class="placeholder">待补充</p>
              {/if}
            </section>

            <section>
              <h3>包 / 类</h3>
              {#if selectedDetail.packages_or_classes?.length}
                <ul>
                  {#each selectedDetail.packages_or_classes as item}
                    <li>{item}</li>
                  {/each}
                </ul>
              {:else}
                <p class="placeholder">待补充</p>
              {/if}
            </section>

            <section>
              <h3>依赖模块</h3>
              {#if selectedDetail.dependencies?.length}
                <ul>
                  {#each selectedDetail.dependencies as item}
                    <li>{item}</li>
                  {/each}
                </ul>
              {:else}
                <p class="placeholder">无</p>
              {/if}
            </section>

            <section>
              <h3>备注</h3>
              <p>{selectedDetail.remarks || '待补充'}</p>
            </section>
          </div>
        {:else}
          <div class="detail-empty">
            <p>请选择左侧模块查看事实信息</p>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
.page { padding: 28px 32px; }
.page-header {
  margin-bottom: 12px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
h2 { font-family: var(--font-headline); font-size: 20px; font-weight: 700; color: var(--text); }
.page-subtitle { font-size: 12px; color: var(--text-muted); margin-top: 3px; max-width: 720px; }
.refresh-button {
  border: none;
  background: var(--primary);
  color: white;
  border-radius: var(--radius);
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--shadow-soft);
  flex-shrink: 0;
}
.refresh-button:disabled {
  opacity: 0.7;
  cursor: progress;
}
.refresh-message {
  margin-bottom: 16px;
  font-size: 12px;
  color: var(--text-muted);
}

.toolbar { display: flex; gap: 12px; margin-bottom: 20px; }
.filter-wrap, .search-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--high);
  border-radius: var(--radius);
  padding: 8px 12px;
}
.search-wrap { flex: 1; }
.search-wrap input {
  flex: 1;
  background: transparent;
  border: none;
  padding: 0;
  font-size: 13px;
}
.filter-wrap select {
  background: transparent;
  border: none;
  min-width: 120px;
  font-size: 13px;
}

.content-shell {
  display: grid;
  grid-template-columns: 3fr 7fr;
  gap: 20px;
  height: calc(100vh - 220px);
  min-height: 0;
}

.items-panel,
.detail-panel {
  min-height: 0;
  height: 100%;
  background: var(--lowest);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-soft);
}

.items-panel {
  overflow: hidden;
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
  height: 100%;
  overflow-y: auto;
  padding: 10px;
}

.system-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.group-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 4px 6px 0;
}

.subsystem-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.subsystem-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  padding: 0 6px;
}

.group-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.submodule-sections {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.submodule-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.submodule-section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.item-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--lowest);
  border-radius: var(--radius-lg);
  text-align: left;
  cursor: pointer;
  box-shadow: var(--shadow-soft);
  transition: box-shadow 0.2s;
  width: 100%;
}
.item-row:hover { box-shadow: var(--shadow-float); }
.item-row.active { outline: 2px solid var(--primary); outline-offset: -1px; }
.item-main { flex: 1; min-width: 0; }
.item-title-row { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.item-name { font-size: 15px; font-weight: 600; color: var(--text); }
.item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.item-desc {
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
}
.chevron { color: var(--text-muted); flex-shrink: 0; }

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
.empty code { background: var(--high); padding: 1px 6px; border-radius: var(--radius-sm); font-size: 12px; }

.detail-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.detail-header {
  display: flex;
  align-items: flex-start;
  padding: 24px 24px 18px;
  border-bottom: 1.5px solid var(--dividers);
  gap: 16px;
}
.d-name { font-family: var(--font-headline); font-weight: 700; font-size: 18px; color: var(--text); margin-bottom: 6px; }
.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: var(--text-muted);
}
.detail-content {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  color: var(--text);
}
.detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: var(--text-muted);
}
section { margin-bottom: 22px; }
h3 { font-size: 13px; font-weight: 700; margin-bottom: 10px; color: var(--text); }
p { line-height: 1.7; font-size: 13px; }
.placeholder { color: var(--text-muted); }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  background: var(--high);
  border-radius: var(--radius);
  overflow: hidden;
}
th, td {
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid var(--dividers);
  vertical-align: top;
}
th { font-weight: 700; color: var(--text); background: rgba(148,163,184,0.08); }
ul { display: flex; flex-direction: column; gap: 8px; padding-left: 18px; }
li { font-size: 13px; line-height: 1.5; }
code {
  margin-left: 8px;
  background: var(--high);
  border-radius: var(--radius-sm);
  padding: 1px 6px;
  font-size: 11px;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .refresh-button {
    align-self: flex-start;
  }

  .content-shell {
    grid-template-columns: 1fr;
    height: auto;
  }

  .items-list,
  .detail-content {
    height: auto;
    max-height: none;
  }
}
</style>
