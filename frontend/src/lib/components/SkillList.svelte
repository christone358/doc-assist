<script>
  import { onMount } from 'svelte';
  import { skillList } from '$lib/stores.js';
  import { skills } from '$lib/api.js';

  let selected = null;

  onMount(async () => {
    const res = await skills.list();
    skillList.set(res.skills || []);
  });
</script>

<div class="page">
  <div class="page-header">
    <h2>可用 Skill 列表</h2>
    <span class="count-badge">{$skillList.length} 个</span>
  </div>

  {#if $skillList.length === 0}
    <div class="empty">
      <span class="material-symbols-outlined" style="font-size:36px;color:var(--dividers);font-variation-settings:'FILL' 0,'wght' 300;">extension_off</span>
      <p>暂无已加载的 Skill</p>
      <p class="empty-hint">请将 Skill 目录放入 <code>skills/</code> 并重启服务</p>
      <p class="empty-hint">参考 <code>skills/SKILL_DEVELOPMENT_GUIDE.md</code> 开发你自己的 Skill</p>
    </div>
  {:else}
    <div class="skill-grid">
      {#each $skillList as skill}
        <button class="skill-card {selected?.id === skill.id ? 'active' : ''}" on:click={() => selected = skill}>
          <div class="skill-icon">
            <span class="material-symbols-outlined" style="font-size:20px;color:var(--primary);font-variation-settings:'FILL' 1,'wght' 400;">extension</span>
          </div>
          <div class="skill-name">{skill.name}</div>
          <div class="skill-desc">{skill.description}</div>
          <div class="skill-tags">
            {#each (skill.tags || []).slice(0,4) as tag}
              <span class="tag">{tag}</span>
            {/each}
          </div>
        </button>
      {/each}
    </div>
  {/if}
</div>

{#if selected}
  <div class="detail-panel">
    <div class="detail-header">
      <div class="detail-title-group">
        <div class="detail-icon">
          <span class="material-symbols-outlined" style="font-size:18px;color:var(--primary);font-variation-settings:'FILL' 1,'wght' 400;">extension</span>
        </div>
        <h3>{selected.name}</h3>
      </div>
      <button class="btn-ghost" on:click={() => selected = null}>
        <span class="material-symbols-outlined" style="font-size:16px;">close</span>
      </button>
    </div>
    <div class="detail-body">
      <p class="desc">{selected.description}</p>
      <div class="meta-group">
        <div class="meta-row">
          <span class="label">类型</span>
          <span class="tag">{selected.type}</span>
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
            <ul>{#each selected.capabilities as c}<li>{c}</li>{/each}</ul>
          </div>
        {/if}
        {#if selected.tags?.length}
          <div class="meta-row">
            <span class="label">标签</span>
            <div class="tags-row">{#each selected.tags as t}<span class="tag">{t}</span>{/each}</div>
          </div>
        {/if}
      </div>
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
.skill-tags { display: flex; flex-wrap: wrap; gap: 4px; }

/* Detail panel */
.detail-panel {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 340px;
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
.detail-body { padding: 20px; overflow-y: auto; flex: 1; }
.desc { color: var(--text-muted); margin-bottom: 20px; line-height: 1.65; font-size: 13px; }
.meta-group { display: flex; flex-direction: column; gap: 12px; }
.meta-row { display: flex; gap: 12px; font-size: 13px; align-items: flex-start; }
.label { color: var(--text-muted); min-width: 48px; font-size: 12px; padding-top: 2px; }
.tags-row { display: flex; flex-wrap: wrap; gap: 4px; }
ul { list-style: disc; padding-left: 16px; }
li { margin-bottom: 4px; }
</style>
