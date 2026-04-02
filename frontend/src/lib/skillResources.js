const RESOURCE_CATEGORY_ORDER = ['script', 'template', 'reference', 'other'];

const RESOURCE_CATEGORY_META = {
  script: { label: '脚本工具', icon: 'terminal' },
  template: { label: '模板文件', icon: 'description' },
  reference: { label: '参考资料', icon: 'menu_book' },
  other: { label: '其他资源', icon: 'folder' },
};

export function groupSkillResources(resources = []) {
  const groups = new Map();

  for (const resource of resources) {
    const category = RESOURCE_CATEGORY_META[resource?.category] ? resource.category : 'other';
    const current = groups.get(category) || [];
    current.push(resource);
    groups.set(category, current);
  }

  return RESOURCE_CATEGORY_ORDER
    .filter((category) => groups.has(category))
    .map((category) => ({
      category,
      label: RESOURCE_CATEGORY_META[category].label,
      icon: RESOURCE_CATEGORY_META[category].icon,
      items: groups.get(category).slice().sort((left, right) => {
        return String(left?.path || '').localeCompare(String(right?.path || ''));
      }),
    }));
}
