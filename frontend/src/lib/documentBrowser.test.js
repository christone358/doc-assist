import test from 'node:test';
import assert from 'node:assert/strict';

import {
  filterFormalDocuments,
  groupDocumentsByType,
  sortVersionsDesc,
} from './documentBrowser.js';

test('filterFormalDocuments only keeps doc_output paths', () => {
  const docs = [
    { doc_type: 'requirements', path: 'doc_output/requirements/A/2026-03-31/v1.0.0.md' },
    { doc_type: 'requirements', path: 'backend/docs/requirements/A/2026-03-31/v1.0.0.md' },
  ];

  assert.deepEqual(filterFormalDocuments(docs), [docs[0]]);
});

test('groupDocumentsByType groups visible documents by canonical type order', () => {
  const sections = groupDocumentsByType([
    {
      doc_type: 'user-manual',
      doc_type_label: '用户手册',
      doc_name: '技能管理模块',
      latest_date: '2026-03-30',
      path: 'doc_output/user-manual/技能管理模块/2026-03-30/v1.0.0.md',
    },
    {
      doc_type: 'requirements',
      doc_type_label: '需求规格',
      doc_name: 'LLM集成管理模块',
      latest_date: '2026-03-31',
      path: 'doc_output/requirements/LLM集成管理模块/2026-03-31/v1.0.0.md',
    },
    {
      doc_type: 'design',
      doc_type_label: '设计方案',
      doc_name: 'LLM集成管理模块',
      latest_date: '2026-03-29',
      path: 'backend/docs/design/LLM集成管理模块/2026-03-29/v1.0.0.md',
    },
  ]);

  assert.deepEqual(
    sections.map((section) => section.doc_type),
    ['requirements', 'user-manual'],
  );
  assert.equal(sections[0].documents[0].doc_name, 'LLM集成管理模块');
});

test('sortVersionsDesc orders version history by version number descending', () => {
  const versions = sortVersionsDesc([
    { version: '1.0.2', updated_at: '2026-03-31T10:00:00Z' },
    { version: '1.0.10', updated_at: '2026-03-31T09:00:00Z' },
    { version: '1.1.0', updated_at: '2026-03-30T09:00:00Z' },
    { version: '1.0.2', updated_at: '2026-03-31T11:00:00Z' },
  ]);

  assert.deepEqual(
    versions.map((item) => `${item.version}@${item.updated_at}`),
    [
      '1.1.0@2026-03-30T09:00:00Z',
      '1.0.10@2026-03-31T09:00:00Z',
      '1.0.2@2026-03-31T11:00:00Z',
      '1.0.2@2026-03-31T10:00:00Z',
    ],
  );
});
