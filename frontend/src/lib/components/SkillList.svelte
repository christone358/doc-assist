<script>
  import { onMount } from 'svelte';
  import { skillList } from '$lib/stores.js';
  import { skills } from '$lib/api.js';
  import { groupSkillResources } from '$lib/skillResources.js';
  import Icon from '$lib/components/Icon.svelte';

  let selected = null;
  let selectedId = null;
  let detailLoading = false;
  let detailError = '';

  onMount(async () => {
    const res = await skills.list();
    skillList.set(res.skills || []);
  });

  async function selectSkill(skill) {
    selectedId = skill.id;
    selected = null;
    detailError = '';
    detailLoading = true;

    try {
      selected = await skills.get(skill.id);
    } catch (error) {
      detailError = error?.message || '技能详情加载失败';
    } finally {
      detailLoading = false;
    }
  }

  function clearSelection() {
    selected = null;
    selectedId = null;
    detailError = '';
    detailLoading = false;
  }

  $: resourceGroups = groupSkillResources(selected?.resources || []);
</script>

<div class="page">
  <div class="page-header">
    <h2>可用 Skill 列表</h2>
    <span class="count-badge">{$skillList.length} 个</span>
  </div>

  {#if $skillList.length === 0}
    <div class="empty">
      <Icon name="extension_off" style="font-size:36px;color:var(--dividers);" />
      <p>暂无已加载的 Skill</p>
      <p class="empty-hint">请将 Skill 目录放入 <code>skills/</code> 并重启服务</p>
      <p class="empty-hint">参考 <code>skills/SKILL_DEVELOPMENT_GUIDE.md</code> 开发你自己的 Skill</p>
    </div>
  {:else}
    <div class="skill-grid">
      {#each $skillList as skill}
        <button class="skill-card {selectedId === skill.id ? 'active' : ''}" on:click={() => selectSkill(skill)}>
          <div class="skill-icon">
            <Icon name="extension" style="font-size:20px;color:var(--primary);" />
          </div>
          <div class="skill-name">{skill.name}</div>
          <div class="skill-desc">{skill.description}</div>
          <div class="skill-meta-line">
            <span class="meta-pill">{skill.type}</span>
            {#if skill.version}
              <span class="meta-text">v{skill.version}</span>
            {/if}
          </div>
        </button>
      {/each}
    </div>
  {/if}
</div>

{#if $skillList.length > 0}
  <div class="detail-panel">
    <div class="detail-header">
      <div class="detail-title-group">
        <div class="detail-icon">
          <Icon name="extension" style="font-size:18px;color:var(--primary);" />
        </div>
        <h3>{selected?.name || 'Skill 详情'}</h3>
      </div>
      <button class="btn-ghost" on:click={clearSelection}>
        <Icon name="close" style="font-size:16px;" />
      </button>
    </div>
    <div class="detail-body">
      {#if detailLoading}
        <div class="detail-empty">
          <Icon name="hourglass_top" spin={true} />
          <p>正在加载技能详情</p>
        </div>
      {:else if detailError}
        <div class="detail-empty">
          <Icon name="error" />
          <p>{detailError}</p>
        </div>
      {:else if !selected}
        <div class="detail-empty">
          <Icon name="left_click" />
          <p>从左侧选择一个 Skill 查看元信息和内部资源</p>
        </div>
      {:else}
        <p class="desc">{selected.description}</p>

        <div class="meta-section">
          <div class="section-title">元信息</div>
          <div class="meta-group">
            <div class="meta-row">
              <span class="label">标识</span>
              <code>{selected.id}</code>
            </div>
            <div class="meta-row">
              <span class="label">类型</span>
              <span class="meta-pill">{selected.type}</span>
            </div>
            {#if selected.version}
              <div class="meta-row">
                <span class="label">版本</span>
                <span>{selected.version}</span>
              </div>
            {/if}
            {#if selected.capabilities?.length}
              <div class="meta-row">
                <span class="label">能力</span>
                <ul>{#each selected.capabilities as capability}<li>{capability}</li>{/each}</ul>
              </div>
            {/if}
          </div>
        </div>

        <div class="resource-section">
          <div class="section-title">内部资源</div>
          {#if resourceGroups.length === 0}
            <div class="resource-empty">当前 Skill 没有可展示的脚本或资源文件</div>
          {:else}
            <div class="resource-groups">
              {#each resourceGroups as group}
                <section class="resource-group">
                  <div class="resource-group-header">
                    <Icon name={group.icon} style="font-size:16px;" />
                    <span>{group.label}</span>
                  </div>
                  <ul class="resource-list">
                    {#each group.items as item}
                      <li class="resource-item">
                        <span class="resource-name">{item.name}</span>
                        <code>{item.path}</code>
                      </li>
                    {/each}
                  </ul>
                </section>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
.page { padding: 28px 32px; max-width: 900px; }

.page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
h2 { font-family: var(--font-headline); font-size: 20px; font-weight: 700; color: var(--text); }
.count-badge {
  background: var(--primary-surface);
  color: var(--primary);
  border-radius: var(--radius-full);
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 600;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  margin-top: 60px;
  text-align: center;
}
.empty p { font-size: 15px; font-weight: 500; color: var(--text); }
.empty-hint { font-size: 13px !important; font-weight: 400 !important; color: var(--text-muted) !important; }
.empty code { background: var(--high); padding: 1px 6px; border-radius: var(--radius-sm); font-size: 12px; }

.skill-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 14px; }

.skill-card {
  background: var(--lowest);
  border-radius: var(--radius-lg);
  padding: 18px;
  text-align: left;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: var(--shadow-soft);
  transition: box-shadow 0.2s, transform 0.15s;
  border: 1.5px solid transparent;
}
.skill-card:hover { box-shadow: var(--shadow-float); transform: translateY(-1px); }
.skill-card.active { border-color: var(--primary); background: var(--primary-surface); }

.skill-icon { margin-bottom: 2px; }
.skill-name { font-weight: 700; font-size: 14px; color: var(--text); font-family: var(--font-headline); }
.skill-desc { color: var(--text-muted); font-size: 12px; line-height: 1.55; }
.skill-meta-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
.meta-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--primary-surface);
  color: var(--primary);
  font-size: 11px;
  font-weight: 600;
}
.meta-text { color: var(--text-muted); font-size: 12px; }

.detail-panel {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 360px;
  background: var(--lowest);
  display: flex;
  flex-direction: column;
  z-index: 50;
  box-shadow: var(--shadow-float);
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 20px 16px;
  border-bottom: 1.5px solid var(--dividers);
}
.detail-title-group { display: flex; align-items: center; gap: 10px; }
.detail-icon {
  width: 34px;
  height: 34px;
  background: var(--primary-surface);
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
}
.detail-header h3 { font-family: var(--font-headline); font-size: 15px; font-weight: 700; color: var(--text); }
.detail-body { padding: 20px; overflow-y: auto; flex: 1; display: flex; flex-direction: column; gap: 20px; }
.detail-empty {
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--text-muted);
  text-align: center;
}
.desc { color: var(--text-muted); margin: 0; line-height: 1.65; font-size: 13px; }
.section-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 10px;
}
.meta-group { display: flex; flex-direction: column; gap: 12px; }
.meta-row { display: flex; gap: 12px; font-size: 13px; align-items: flex-start; }
.label { color: var(--text-muted); min-width: 48px; font-size: 12px; padding-top: 2px; }
ul { list-style: disc; padding-left: 16px; margin: 0; }
li { margin-bottom: 4px; }
code {
  background: var(--high);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 12px;
}
.resource-empty {
  color: var(--text-muted);
  font-size: 13px;
  background: var(--high);
  border-radius: var(--radius);
  padding: 12px;
}
.resource-groups { display: flex; flex-direction: column; gap: 14px; }
.resource-group {
  border: 1px solid var(--dividers);
  border-radius: var(--radius);
  padding: 12px;
}
.resource-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 8px;
}
.resource-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.resource-item {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.resource-name {
  font-size: 13px;
  color: var(--text);
  font-weight: 500;
}
</style>
