import test from 'node:test';
import assert from 'node:assert/strict';

import { groupSkillResources } from './skillResources.js';

test('groupSkillResources orders known categories and sorts entries by path', () => {
  const groups = groupSkillResources([
    { category: 'other', path: 'notes/example.md', name: 'example.md' },
    { category: 'script', path: 'scripts/helper.py', name: 'helper.py' },
    { category: 'reference', path: 'references/a.md', name: 'a.md' },
    { category: 'script', path: 'scripts/main.py', name: 'main.py' },
  ]);

  assert.deepEqual(
    groups.map((group) => group.category),
    ['script', 'reference', 'other'],
  );
  assert.deepEqual(
    groups[0].items.map((item) => item.path),
    ['scripts/helper.py', 'scripts/main.py'],
  );
});

test('groupSkillResources falls back unknown categories into other', () => {
  const groups = groupSkillResources([
    { category: 'misc', path: 'docs/readme.md', name: 'readme.md' },
  ]);

  assert.equal(groups.length, 1);
  assert.equal(groups[0].category, 'other');
  assert.equal(groups[0].items[0].path, 'docs/readme.md');
});
