## Context

当前系统已经在代码层引入了 `doc_output/` 作为新的正式输出路径，但实际行为仍然没有完全收敛：

- 正式文档输出与历史查询来源仍可能混用 legacy 目录
- 文档结果管理页面没有完全按实际输出的 canonical 文档类型管理结果
- `backend/docs/` 中仍保留旧的输出文档，容易让用户与 Agent 混淆“哪个才是正式版本”

同时，`backend/docs/conversations/` 仍承担会话记录持久化职责，因此“删除 backend 中的输出文档”不能等同于“整个 backend/docs 目录删除”，而应精确限定为“先迁移其中的正式输出文档，再删除 legacy 正式输出目录，并停用该目录作为正式文档来源”。

## Goals / Non-Goals

**Goals:**
- 将 `doc_output/` 收敛为正式文档输出和历史正式版本读取的唯一来源
- 停止在 `backend/docs/` 中继续保留或写入正式输出文档
- 优化文档结果管理页面，使其按实际输出的 canonical 文档类型管理文档
- 在需求规格与用户手册类型下支持按模块过滤和搜索
- 让 Agent 在修改/续写场景中只从 `doc_output/` 加载历史正式版本作为写作输入

**Non-Goals:**
- 不重构会话日志目录，`backend/docs/conversations/` 不在本次改动范围内
- 不引入新的存储后端或数据库
- 不改变草稿驻留内存、显式保存才落盘的交互模型
- 不在本次改动中新增复杂的迁移 UI 或批量导入工具

## Decisions

### 决策 1：`doc_output/` 成为正式文档单一可信源

所有正式版本的保存、列表、历史加载都只以 `doc_output/` 为准。

**备选：** 保留 `doc_output/` 与 `backend/docs/` 双读策略。  
**否决原因：** 双源会让页面展示和 Agent 写作输入继续存在歧义，无法建立稳定的正式版本口径。

### 决策 2：精确区分“正式输出文档”和“会话持久化数据”

`backend/docs/` 中：

- `conversations/` 保留，继续作为会话日志目录
- 其余用于正式输出的类型目录（如 `requirements/`、`design/`、`general/` 等）视为 legacy 输出，先迁移到 `doc_output/`，再停止使用并清理

**备选：** 整个 `backend/docs/` 一并删除。  
**否决原因：** 会误删当前仍在使用的会话日志数据。

### 决策 3：文档结果管理页以“实际输出类型”作为展示维度

页面筛选与分组统一基于实际输出的 canonical 文档类型，而不是历史目录名、口语别名或旧路径。

**原因：** 用户关心的是“现在系统实际生成了哪类正式文档”，而不是早期曾经用过什么 legacy 类型名。

### 决策 4：需求规格与用户手册提供模块维度过滤

文档结果管理页在展示 `requirements` 与 `user-manual` 两类文档时，增加模块过滤 / 搜索能力；搜索目标是文档系列的模块名（canonical 名称）及其别名。

**备选：** 所有文档类型统一支持模块过滤。  
**否决原因：** 设计方案、测试方案、API 文档不一定稳定以“模块”作为唯一管理维度，强行统一会引入无效筛选。

### 决策 5：Agent 的历史正式版本工具只查询 `doc_output/`

`list_saved_documents` 与 `load_saved_document` 的正式版本来源收敛到 `doc_output/`，不再把 legacy 输出目录当成写作输入来源。

**备选：** 继续兼容读取 legacy 输出目录。  
**否决原因：** 会破坏“单一正式版本来源”的目标，并导致 Agent 修改时可能基于过期内容继续写作。

### 决策 6：模块过滤能力由后端查询接口承接

需求规格与用户手册的模块过滤 / 搜索不只在前端本地过滤，而应由文档列表查询接口支持 `doc_type + module filter/search` 语义。

**备选：** 前端拿到全量结果后再本地过滤。  
**否决原因：** 一旦结果集增大、分页引入或数据按需加载，本地过滤无法保证检索能力与规范一致。

## Risks / Trade-offs

**[Risk] 清理 backend legacy 输出后，个别手工依赖旧路径的流程会失效**  
→ Mitigation：先完成迁移，再切断旧路径；在变更说明中明确 `doc_output/` 是新的唯一正式路径。

**[Risk] 现有测试或脚本可能仍假设正式输出存在于 `backend/docs/`**  
→ Mitigation：统一更新测试夹具、接口断言和页面展示预期。

**[Trade-off] 模块过滤只覆盖部分文档类型**  
→ Mitigation：在页面上仅对 `requirements` / `user-manual` 显示模块搜索控件，避免用户误解其余类型也具备同样维度。

**[Trade-off] 迁移 legacy 正式文档会增加一次性处理成本**  
→ Mitigation：迁移范围仅限正式输出目录，不涉及 `backend/docs/conversations/`；迁移完成后再切换读取口径。

## Migration Plan

1. 将 `backend/docs/` 下的 legacy 正式输出迁移到 `doc_output/`
2. 收敛 `doc_version_service` 的读取与写入根目录到 `doc_output/`
3. 调整 Agent 历史文档发现/加载工具，仅查询 `doc_output/`
4. 扩展文档列表查询接口，支持 `requirements` / `user-manual` 的模块过滤与搜索
5. 调整文档结果管理页面，仅展示 `doc_output/` 下的正式输出，并按实际输出类型筛选
6. 清理 `backend/docs/` 下的 legacy 输出文档目录，但保留 `backend/docs/conversations/`
7. 更新测试，验证保存、列表、加载和页面展示均以 `doc_output/` 为唯一正式来源

## Open Questions

- 文档结果管理页面是否需要增加“来源说明”文案，明确告诉用户当前仅展示 `doc_output/` 中的正式版本？
