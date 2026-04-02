## Context

当前 Skill 管理链路由 `backend/skill/manager.py` 扫描 `skills/` 目录、解析 `skill.md` frontmatter，并通过 `/api/v1/skills` 暴露给前端 `SkillList.svelte`。现状存在三个问题：

- 元信息边界不明确：后端把 `tags`、`skill_md_path` 等字段与正式元信息并列暴露，前端也直接渲染标签区域
- Skill 资源不可见：虽然仓库中的 Skill 已经存在 `scripts/`、`templates/`、`references/` 等目录，但技能管理页无法展示这些内部资源
- 目录约定不一致：文档里同时出现 `reference/` 与 `references/` 两种命名，现有 Skill 也存在新旧结构混用

这次变更横跨 Skill 解析模型、技能管理接口、前端详情面板和开发文档，属于典型的跨模块契约收敛。

## Goals / Non-Goals

**Goals:**

- 明确 Skill 管理“正式元信息”的范围，避免 UI 展示非契约字段
- 从 Skill 目录生成稳定的资源清单，支持展示脚本工具、模板、参考资料和其他辅助文件
- 移除 `tags` 在 Skill 管理中的解析和展示地位，同时保留对历史 Skill 文件的兼容读取
- 统一前端信息架构，将“元信息”和“内部资源”分区展示

**Non-Goals:**

- 不在本次变更中实现资源文件预览、下载或在线编辑
- 不改变 Agent 选择 Skill 的主流程，也不新增基于资源清单的调度逻辑
- 不对 Skill 正文内容做全文索引或搜索能力建设

## Decisions

### Decision 1: 用显式白名单定义 Skill 元信息契约

Skill 管理接口只返回受支持的元信息字段：`id`、`name`、`description`、`type`、`version`、`capabilities`。其中 `id` 用于系统标识，详情面板可按需展示；`skill_md_path`、未知 frontmatter 字段和 legacy `tags` 均不进入元信息展示面。

选择白名单而不是“原样转发所有 frontmatter”，是为了让前后端围绕稳定契约协作，并避免未来 Skill 作者随意增加字段后直接污染管理页面。

备选方案：
- 透传全部 frontmatter：实现最省事，但会继续放大“什么算元信息”的歧义
- 在前端过滤字段：无法阻止接口继续暴露内部路径和历史遗留字段，边界仍然松散

### Decision 2: 通过文件系统扫描生成资源清单，并统一为相对路径模型

每个 Skill 在加载时额外生成资源清单，只编目 `skill.md` 之外的文件，忽略隐藏文件与目录。资源条目至少包含：

- `category`：`script`、`template`、`reference`、`other`
- `path`：相对 Skill 根目录的路径，例如 `scripts/main.py`
- `name`：展示名，默认取文件名

分类规则按顶层目录决定：

- `scripts/` → `script`
- `templates/` → `template`
- `reference/` 或 `references/` → `reference`
- 其他文件或目录下的文件 → `other`

资源清单使用相对路径，而不是绝对路径，避免把本机路径直接暴露到 UI 和 API。

备选方案：
- 在 `skill.md` 中手工声明资源：维护成本高，容易与实际文件结构失真
- 只展示目录名不展示文件：用户仍然无法判断 Skill 内实际有哪些脚本或模板

### Decision 3: 对 legacy `tags` 采用“静默忽略”迁移策略

解析器不再把 `tags`/`Tags` 读取为 Skill 元信息，也不再返回给技能管理接口。若历史 Skill 文件仍保留该字段，系统继续允许加载 Skill，但标签字段不会进入 API、UI 或测试契约。

这样可以避免一次性阻断现有 Skill，同时明确告知维护者：标签已退出正式支持范围。

备选方案：
- 发现 `tags` 就报错：迁移更彻底，但会让现有 Skill 无法加载，改动过于激进
- 继续返回 `tags` 但前端不展示：实现简单，但没有真正删除标签链路

### Decision 4: 技能管理页采用“摘要卡片 + 详情分区”布局

列表卡片仅展示摘要元信息：名称、描述、类型和版本。详情面板分为两个区块：

- 元信息区：仅展示受支持元信息字段
- 内部资源区：按 `脚本工具 / 模板 / 参考资料 / 其他资源` 分组列出文件

这样既能满足“只显示元信息”的要求，也能让用户在同一视图中理解 Skill 的内部资产，而不会把资源误当成元信息。

备选方案：
- 把资源混在元信息区一起展示：继续制造信息混叠
- 资源单独做新页面：信息架构更重，不符合本次优化范围

## Risks / Trade-offs

- [Risk] 现有文档和示例 Skill 仍包含 `tags` 字段，短期内会与新契约不一致 → Mitigation：同步更新 `skills/README.md`、`skills/SKILL_DEVELOPMENT_GUIDE.md`、示例 Skill 和测试样例
- [Risk] `reference/` 与 `references/` 双命名会让资源分类实现变复杂 → Mitigation：资源分类层同时兼容两种目录名，对外统一显示为“参考资料”
- [Risk] 新增资源扫描后，Skill 加载成本略有上升 → Mitigation：仅扫描单个 Skill 目录下的本地文件，不读取文件内容，复杂度保持在线性范围
- [Risk] 去掉标签后，用户可能误以为搜索能力被削弱 → Mitigation：在设计和文档中明确说明标签从未形成稳定能力，本次仅收敛无效链路

## Migration Plan

1. 扩展 Skill 数据模型，引入资源条目结构，并将标签从正式元信息中移除
2. 更新 `SkillLoader` 的解析与扫描逻辑，输出受控元信息和资源清单
3. 调整 `/api/v1/skills` 与 `/api/v1/skills/{skill_id}` 的响应模型，确保不再暴露标签和绝对路径
4. 重构 `SkillList.svelte` 的卡片与详情面板，移除标签区并新增资源区
5. 更新开发指南、README、示例 Skill 与测试，清除对 `tags` 的依赖
6. 回归验证：空资源 Skill、包含 `scripts/` 的 Skill、包含 `templates/` / `references/` 的 Skill、含 legacy `tags` 的 Skill

回滚策略：

- 若前端展示或接口兼容性出现问题，可回退到变更前的 `SkillInfo` 模型和 `SkillList.svelte`
- 由于本次不涉及持久化存储迁移，回滚只需恢复代码与文档

## Open Questions

- 资源清单是否需要在列表页显示汇总数量，还是仅在详情面板显示明细；本次设计默认只在详情中展示明细
- 是否需要将 `author`、`constraints` 等字段纳入未来的正式元信息白名单；本次先以现有已稳定实现的字段为准，不扩大范围
