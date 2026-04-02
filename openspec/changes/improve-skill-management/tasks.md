## 1. 后端 Skill 数据契约

- [x] 1.1 调整 `backend/agent/models.py` 中的 Skill 响应模型，移除标签字段并新增资源清单结构
- [x] 1.2 重构 `backend/skill/manager.py` 的 Skill 解析逻辑，使用元信息白名单并忽略 legacy `tags`
- [x] 1.3 在 `backend/skill/manager.py` 中实现 Skill 资源扫描与分类，支持 `scripts/`、`templates/`、`reference/`、`references/` 和其他资源文件
- [x] 1.4 更新 Skill 列表与详情返回内容，确保接口不再暴露绝对路径和非契约字段

## 2. 技能管理页面展示

- [x] 2.1 重构 `frontend/src/lib/components/SkillList.svelte` 的卡片摘要区，只展示受支持的 Skill 元信息
- [x] 2.2 移除技能详情中的标签区域和所有标签相关交互
- [x] 2.3 在技能详情面板中新增“内部资源”分组展示，分别呈现脚本工具、模板、参考资料和其他资源文件
- [x] 2.4 为无资源 Skill 和无选中 Skill 的场景补充空状态与展示兜底

## 3. 文档与示例更新

- [x] 3.1 更新 `skills/README.md`，明确新的元信息范围与资源目录约定
- [x] 3.2 更新 `skills/SKILL_DEVELOPMENT_GUIDE.md`，移除 `tags` 说明并补充资源清单规范
- [x] 3.3 清理仓库内示例 Skill 的 legacy `tags` 字段，确保示例与新契约一致

## 4. 验证

- [x] 4.1 更新 `backend/tests/test_skill_framework.py`，覆盖标签忽略、资源扫描和空资源清单场景
- [x] 4.2 为技能管理页补充或更新前端验证，确认标签不再显示且资源分组可见
- [ ] 4.3 运行相关测试并手动检查技能管理页，确认列表、详情和资源展示符合规格
