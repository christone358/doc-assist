export const TYPE_ORDER = [
  'requirements',
  'design',
  'api',
  'test-plan',
  'user-manual',
  'general',
];

export const TYPE_CONFIG = {
  requirements: { color: '#6366f1', bg: 'rgba(99,102,241,0.1)', label: '需求规格' },
  design: { color: '#10b981', bg: 'rgba(16,185,129,0.1)', label: '设计方案' },
  api: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', label: 'API 文档' },
  'test-plan': { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', label: '测试方案' },
  'user-manual': { color: '#0ea5e9', bg: 'rgba(14,165,233,0.1)', label: '用户手册' },
  general: { color: '#64748b', bg: 'rgba(100,116,139,0.1)', label: '通用文档' },
};

export function getTypeMeta(docType, fallbackLabel = docType) {
  return TYPE_CONFIG[docType] || {
    color: '#64748b',
    bg: 'rgba(100,116,139,0.1)',
    label: fallbackLabel,
  };
}

export function filterFormalDocuments(documents = []) {
  return documents.filter((doc) => {
    const path = typeof doc?.path === 'string' ? doc.path : '';
    return path.startsWith('doc_output/');
  });
}

function versionTuple(version) {
  const text = String(version || '').replace(/^v/i, '');
  const parts = text.split('.').map((part) => Number.parseInt(part, 10));
  return [
    Number.isFinite(parts[0]) ? parts[0] : 0,
    Number.isFinite(parts[1]) ? parts[1] : 0,
    Number.isFinite(parts[2]) ? parts[2] : 0,
  ];
}

export function sortVersionsDesc(versions = []) {
  return versions.slice().sort((left, right) => {
    const leftTuple = versionTuple(left?.version);
    const rightTuple = versionTuple(right?.version);

    for (let index = 0; index < 3; index += 1) {
      if (leftTuple[index] !== rightTuple[index]) {
        return rightTuple[index] - leftTuple[index];
      }
    }

    return String(right?.updated_at || right?.date || '').localeCompare(
      String(left?.updated_at || left?.date || ''),
    );
  });
}

export function groupDocumentsByType(documents = [], filterType = '') {
  const groups = new Map();
  const visibleDocs = filterFormalDocuments(documents).filter((doc) => {
    return !filterType || doc.doc_type === filterType;
  });

  for (const doc of visibleDocs) {
    const existing = groups.get(doc.doc_type) || [];
    existing.push(doc);
    groups.set(doc.doc_type, existing);
  }

  const orderedTypes = TYPE_ORDER.filter((type) => groups.has(type));
  for (const type of groups.keys()) {
    if (!orderedTypes.includes(type)) {
      orderedTypes.push(type);
    }
  }

  return orderedTypes.map((docType) => {
    const docs = (groups.get(docType) || []).slice().sort((left, right) => {
      return `${right.latest_date}:${right.doc_name}`.localeCompare(`${left.latest_date}:${left.doc_name}`);
    });
    const label = docs[0]?.doc_type_label || getTypeMeta(docType).label;
    return {
      doc_type: docType,
      label,
      documents: docs,
    };
  });
}
