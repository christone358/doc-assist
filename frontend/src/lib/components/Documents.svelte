<script>
  import { onMount } from 'svelte';
  import { docList, notify } from '$lib/stores.js';
  import { documents } from '$lib/api.js';
  import {
    getTypeMeta,
    groupDocumentsByType,
    sortVersionsDesc,
    TYPE_ORDER,
  } from '$lib/documentBrowser.js';

  let selectedDoc = null;
  let versions = [];
  let filterType = '';
  let documentItems = [];

  const typeOptions = [
    { value: '', label: '全部类型', color: '#334155', bg: 'rgba(148,163,184,0.16)' },
    ...TYPE_ORDER.map((type) => {
      const meta = getTypeMeta(type);
      return {
        value: type,
        label: meta.label,
        color: meta.color,
        bg: meta.bg,
      };
    }),
  ];

  $: sections = groupDocumentsByType(documentItems, filterType);

  onMount(() => refresh());

  async function refresh() {
    const res = await documents.list(filterType || undefined);
    documentItems = res.documents || [];
    docList.set(documentItems);

    if (
      selectedDoc &&
      !documentItems.some(
        (doc) => doc.doc_type === selectedDoc.doc_type && doc.doc_name === selectedDoc.doc_name,
      )
    ) {
      selectedDoc = null;
      versions = [];
    }
  }

  function handleTypeChange(nextType) {
    filterType = nextType;
    refresh();
  }

  async function selectDoc(doc) {
    selectedDoc = doc;
    const res = await documents.versions(doc.doc_type, doc.doc_name);
    versions = sortVersionsDesc(
      (res.versions || []).filter((version) => version.path?.startsWith('doc_output/')),
    );
  }

  function closeModal() {
    selectedDoc = null;
    versions = [];
  }

  function copyPath(path) {
    navigator.clipboard?.writeText(path);
    notify('success', '路径已复制');
  }

  function formatUpdatedAt(value) {
    if (!value) {
      return '-';
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(date);
  }
</script>

<div class="page">
  <div class="page-header">
    <h2>文档版本管理</h2>
    <p class="page-subtitle">仅展示 `doc_output/` 下的正式输出文档，并按实际文档类型管理。</p>
  </div>

  <div class="controls-panel">
    <div class="type-filter-panel">
      <div class="panel-label">文档类型</div>
      <div class="type-chip-list">
        {#each typeOptions as option}
          <button
            class="type-chip {filterType === option.value ? 'active' : ''}"
            type="button"
            style={`--chip-color:${option.color};--chip-bg:${option.bg};`}
            on:click={() => handleTypeChange(option.value)}
          >
            {option.label}
          </button>
        {/each}
      </div>
    </div>
  </div>

  {#if sections.length === 0}
    <div class="empty">
      <span class="material-symbols-outlined empty-icon">folder_open</span>
      <p>暂无正式输出文档</p>
      <p class="empty-hint">保存为正式版本后，这里会按文档类型自动归类展示。</p>
    </div>
  {:else}
    <div class="sections">
      {#each sections as section}
        {@const typeMeta = getTypeMeta(section.doc_type, section.label)}
        <section class="type-section">
          <div class="section-header">
            <div class="section-title-wrap">
              <span class="section-dot" style={`background:${typeMeta.color}`}></span>
              <h3>{section.label}</h3>
            </div>
            <span class="section-count">{section.documents.length} 份文档</span>
          </div>

          <div class="doc-list">
            {#each section.documents as doc}
              {@const tc = getTypeMeta(doc.doc_type, doc.doc_type_label)}
              <div class="doc-row {selectedDoc?.doc_name === doc.doc_name && selectedDoc?.doc_type === doc.doc_type ? 'selected' : ''}">
                <div class="doc-icon-wrap" style={`background:${tc.bg}`}>
                  <span class="material-symbols-outlined doc-icon" style={`color:${tc.color}`}>description</span>
                </div>
                <div class="doc-info">
                  <div class="doc-name">{doc.doc_name}</div>
                  <div class="doc-meta">
                    <span class="type-badge" style={`background:${tc.bg};color:${tc.color}`}>
                      {doc.doc_type_label || tc.label}
                    </span>
                    <span class="meta-sep">·</span>
                    <span class="meta-text">最新版本 v{doc.latest_version}</span>
                    <span class="meta-sep">·</span>
                    <span class="meta-text">更新时间 {formatUpdatedAt(doc.latest_updated_at || doc.latest_date)}</span>
                  </div>
                </div>
                <div class="doc-path-text">{doc.path}</div>
                <div class="doc-actions">
                  <button class="btn-ghost sm" type="button" on:click={() => selectDoc(doc)}>
                    <span class="material-symbols-outlined action-icon">history</span>
                    版本历史
                  </button>
                  <button class="btn-ghost sm" type="button" on:click={() => copyPath(doc.path)}>
                    <span class="material-symbols-outlined action-icon">content_copy</span>
                    复制路径
                  </button>
                </div>
              </div>
            {/each}
          </div>
        </section>
      {/each}
    </div>
  {/if}
</div>

{#if selectedDoc}
  <div
    class="overlay"
    role="button"
    tabindex="0"
    aria-label="关闭版本历史"
    on:click|self={closeModal}
    on:keydown={(event) => {
      if (event.key === 'Escape' || event.key === 'Enter' || event.key === ' ') {
        closeModal();
      }
    }}
  >
    <div class="modal">
      <div class="modal-header">
        <div>
          <h3>{selectedDoc.doc_name}</h3>
          <span class="modal-subtitle">版本历史</span>
        </div>
        <button class="btn-ghost" type="button" on:click={closeModal}>
          <span class="material-symbols-outlined action-icon">close</span>
        </button>
      </div>

      {#if versions.length === 0}
        <p class="empty-modal">暂无版本记录</p>
      {:else}
        <div class="version-list">
          {#each versions as version}
            <div class="version-row">
              <div class="ver-badge">v{version.version}</div>
              <div class="ver-info">
                <span class="ver-date">更新时间 {formatUpdatedAt(version.updated_at || version.date)}</span>
                <span class="ver-path">{version.path}</span>
              </div>
              <button class="btn-ghost sm" type="button" on:click={() => copyPath(version.path)}>
                <span class="material-symbols-outlined action-icon">content_copy</span>
              </button>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .page {
    padding: 28px 32px;
  }

  .page-header {
    margin-bottom: 24px;
  }

  h2 {
    font-family: var(--font-headline);
    font-size: 20px;
    font-weight: 700;
    color: var(--text);
  }

  .page-subtitle {
    margin-top: 6px;
    color: var(--text-muted);
    font-size: 13px;
  }

  .controls-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 24px;
  }

  .type-filter-panel {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 18px;
    background: var(--high);
    border-radius: var(--radius-lg);
    padding: 14px 16px;
  }

  .panel-label {
    min-width: 72px;
    font-size: 12px;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.04em;
  }

  .type-chip-list {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    justify-content: flex-end;
  }

  .type-chip {
    border: 1px solid transparent;
    background: rgba(255, 255, 255, 0.72);
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 600;
    padding: 8px 14px;
    border-radius: 999px;
    transition: all 0.18s ease;
  }

  .type-chip:hover {
    border-color: var(--chip-color);
    color: var(--chip-color);
    background: var(--chip-bg);
  }

  .type-chip.active {
    border-color: var(--chip-color);
    color: var(--chip-color);
    background: var(--chip-bg);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--chip-color) 16%, transparent);
  }

  .action-icon,
  .doc-icon,
  .empty-icon {
    font-size: 16px;
  }

  .empty-icon {
    font-size: 36px;
    color: var(--dividers);
    font-variation-settings: 'FILL' 0, 'wght' 300;
  }

  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    margin-top: 60px;
    text-align: center;
  }

  .empty p {
    font-size: 15px;
    font-weight: 500;
    color: var(--text);
  }

  .empty-hint,
  .empty-modal {
    font-size: 13px;
    color: var(--text-muted);
    font-weight: 400;
  }

  .sections {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .type-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .section-title-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .section-title-wrap h3 {
    font-family: var(--font-headline);
    font-size: 16px;
    font-weight: 700;
    color: var(--text);
  }

  .section-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
  }

  .section-count {
    font-size: 12px;
    color: var(--text-muted);
  }

  .doc-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .doc-row {
    display: flex;
    align-items: center;
    gap: 14px;
    background: var(--lowest);
    border-radius: var(--radius-lg);
    padding: 14px 18px;
    box-shadow: var(--shadow-soft);
    transition: box-shadow 0.2s;
  }

  .doc-row:hover {
    box-shadow: var(--shadow-float);
  }

  .doc-row.selected {
    outline: 2px solid var(--primary);
    outline-offset: -1px;
  }

  .doc-icon-wrap {
    width: 40px;
    height: 40px;
    border-radius: var(--radius);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .doc-icon {
    font-size: 18px;
    font-variation-settings: 'FILL' 1, 'wght' 400;
  }

  .doc-info {
    flex: 1;
    min-width: 0;
  }

  .doc-name {
    font-weight: 600;
    font-size: 14px;
    color: var(--text);
    margin-bottom: 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .doc-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .type-badge {
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    font-size: 11px;
    font-weight: 600;
  }

  .meta-sep {
    color: var(--dividers);
  }

  .meta-text {
    font-size: 12px;
    color: var(--text-muted);
  }

  .doc-path-text {
    font-family: monospace;
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 240px;
    flex-shrink: 0;
  }

  .doc-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }

  .sm {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 5px 10px;
    font-size: 12px;
  }

  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.4);
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
    width: 600px;
    max-width: 95vw;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: var(--shadow-float);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
  }

  .modal-header h3 {
    font-family: var(--font-headline);
    font-size: 16px;
    font-weight: 700;
    color: var(--text);
  }

  .modal-subtitle {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
    display: block;
  }

  .version-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .version-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 14px;
    background: var(--base);
    border-radius: var(--radius);
  }

  .ver-badge {
    background: var(--primary-surface);
    color: var(--primary);
    border-radius: var(--radius-sm);
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 700;
    flex-shrink: 0;
  }

  .ver-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
    flex: 1;
  }

  .ver-date {
    font-size: 12px;
    color: var(--text);
  }

  .ver-path {
    font-family: monospace;
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  @media (max-width: 900px) {
    .page {
      padding: 20px 16px;
    }

    .type-filter-panel,
    .doc-row {
      flex-direction: column;
      align-items: stretch;
    }

    .type-chip-list,
    .doc-actions {
      justify-content: flex-start;
    }

    .doc-path-text {
      min-width: 0;
      max-width: none;
      width: 100%;
    }

    .section-header {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
