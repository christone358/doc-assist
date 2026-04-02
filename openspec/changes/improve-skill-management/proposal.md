## Why

当前技能管理页把 Skill 的元信息、标签和说明性内容混在一起展示，信息边界不清晰；同时页面也看不到 Skill 目录内实际可用的脚本和资源文件，导致用户难以判断一个 Skill 到底包含哪些可执行能力和辅助材料。

现有 `tags` 字段来源不清、实现价值不明确，已经演变成一条难以解释的额外链路。现在需要明确 Skill 管理的数据契约：只展示受支持的元信息，移除标签能力，并补上技能内部资源清单。

## What Changes

- 收敛 Skill 管理接口返回的元信息范围，仅保留系统正式支持的字段；不属于元信息契约的内容不再进入技能面板
- **BREAKING** 移除 Skill 标签字段的解析、返回、展示与相关文档约定；已有 Skill frontmatter 中的 `tags` 不再作为系统能力的一部分
- 为每个 Skill 增加资源清单展示，至少覆盖 `scripts/`、`templates/`、`references/` 等目录下的文件，以及其他可识别的辅助资源
- 更新技能管理页面的列表与详情面板，使其区分“元信息”和“内部资源”，避免将资源文件误显示为元信息
- 更新 Skill 开发文档与测试，明确新的元信息边界和资源发现规则

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `skill-framework`: 调整 Skill 元信息契约，移除标签字段，并定义 Skill 目录内部资源的可发现规则
- `skill-management`: Skill 管理系统返回受控元信息与资源清单，避免暴露非契约化字段
- `web-ui`: Skill 管理页面仅展示受支持元信息，并新增脚本工具与资源文件展示区域

## Impact

- `backend/agent/models.py`
- `backend/skill/manager.py`
- `backend/main.py` 的 `/api/v1/skills` 与 `/api/v1/skills/{skill_id}` 返回内容
- `frontend/src/lib/components/SkillList.svelte`
- `skills/README.md`、`skills/SKILL_DEVELOPMENT_GUIDE.md` 及现有示例 Skill frontmatter
- `backend/tests/test_skill_framework.py` 及相关前端/接口验证
