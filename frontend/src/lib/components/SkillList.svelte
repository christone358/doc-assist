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
    <span class="tag">{$skillList.length} 个</span>
  </div>

  {#if $skillList.length === 0}
    <div class="empty">
      <p>暂无已加载的 Skill。</p>
      <p>请将 Skill 目录放入 <code>skills/</code> 并重启服务。</p>
      <p>参考 <code>skills/SKILL_DEVELOPMENT_GUIDE.md</code> 开发你自己的 Skill。</p>
    </div>
  {:else}
    <div class="skill-grid">
      {#each $skillList as skill}
        <button class="skill-card {selected?.id === skill.id ? 'active' : ''}" on:click={() => selected = skill}>
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
      <h3>{selected.name}</h3>
      <button class="btn-ghost" on:click={() => selected = null}>关闭</button>
    </div>
    <div class="detail-body">
      <p class="desc">{selected.description}</p>
      <div class="meta-row"><span class="label">类型</span><span>{selected.type}</span></div>
      {#if selected.version}
        <div class="meta-row"><span class="label">版本</span><span>{selected.version}</span></div>
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
          <div>{#each selected.tags as t}<span class="tag">{t}</span>{/each}</div>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
.page { padding: 20px; }
.page-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
h2 { font-size: 18px; font-weight: 600; }
.empty { color: var(--text-muted); line-height: 2.2; margin-top: 40px; text-align: center; }
.empty code { background: var(--surface2); padding: 2px 6px; border-radius: 4px; }

.skill-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.skill-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 14px; text-align: left; cursor: pointer; transition: border-color 0.15s;
  display: flex; flex-direction: column; gap: 6px;
}
.skill-card:hover { border-color: var(--accent); }
.skill-card.active { border-color: var(--accent); background: var(--surface2); }
.skill-name { font-weight: 500; font-size: 14px; }
.skill-desc { color: var(--text-muted); font-size: 12px; line-height: 1.5; }
.skill-tags { display: flex; flex-wrap: wrap; gap: 4px; }

.detail-panel {
  position: fixed; right: 0; top: 0; bottom: 0; width: 320px;
  background: var(--surface); border-left: 1px solid var(--border);
  display: flex; flex-direction: column; z-index: 50;
}
.detail-header { display: flex; justify-content: space-between; align-items: center; padding: 16px; border-bottom: 1px solid var(--border); }
.detail-header h3 { font-size: 15px; font-weight: 600; }
.detail-body { padding: 16px; overflow-y: auto; flex: 1; }
.desc { color: var(--text-muted); margin-bottom: 16px; line-height: 1.6; }
.meta-row { display: flex; gap: 12px; margin-bottom: 10px; font-size: 13px; }
.label { color: var(--text-muted); min-width: 50px; }
ul { list-style: disc; padding-left: 16px; }
li { margin-bottom: 4px; }
</style>
