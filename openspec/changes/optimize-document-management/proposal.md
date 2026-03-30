## Why

当前“保存为正式版本”的落盘路径、历史加载路径和前端展示路径并不统一：正式保存与 `load_saved_document` 依赖的查询规则存在偏差，导致用户保存后的文档不一定能被后续修改流程稳定发现。

同时，文档类型和写作对象名称缺少统一归一规则。现实输入中，用户会混用“测试方案 / 测试计划”“用户手册 / 操作手册”，也会对同一对象混用“模块 / 类 / 包 / 管理模块 / 集成模块”等称呼。结果是同一对象被拆成多个目录，历史版本查询和结果展示都出现割裂。

这类问题已经进入“存储模型与命名规则”的设计层面，应该先形成明确方案，再进入实现和验证。

## What Changes

- **统一**正式版本存储根目录：将“保存为正式版本”的官方落盘路径收敛为仓库根目录下的 `doc_output/`
- **统一**文档分类模型：定义 canonical 文档类型集合，并建立类型别名映射，覆盖 `requirements`、`design`、`test-plan`、`user-manual`、`api`、`general`
- **新增**文档系列归一规则：对文档标题执行“文档后缀剥离 + 对象名称规整 + 别名归档”，将同一对象的多种叫法映射到同一文档系列
- **统一**保存、列表、加载链路：`save-draft`、`list_documents`、`list_versions`、`load_saved_document` 使用同一套路径与名称解析逻辑
- **兼容**历史数据读取：保留对旧目录（如 `backend/docs/`、`docs/`）的读取兼容，但新版本只写入 `doc_output/`
- **优化**文档管理页展示：按 canonical 文档类型过滤与展示，显示实际保存路径、版本、日期和别名信息

## Capabilities

### Modified Capabilities

- `document-version-management`：统一正式版本的存储根目录、目录层级、名称归一与历史读取兼容策略
- `web-ui`：文档管理界面改为展示 canonical 分类、canonical 名称和真实保存路径

### New Capabilities

- `document-series-normalization`：系统可识别“同一对象不同叫法”，并将其归入同一文档系列，覆盖需求规格、设计方案、测试方案、用户手册等文档类型

## Impact

- `backend/doc_version_service.py` — 文档保存、查询、加载的统一入口与名称归一逻辑
- `backend/main.py` — 保存正式版本时更新 writing_state 的 canonical 名称与类型
- `backend/agent/adk/saved_doc_tools.py` — 历史加载使用 canonical 文档名称继续衔接
- `frontend/src/lib/api.js` — 文档接口参数编码与路径访问一致化
- `frontend/src/lib/components/Documents.svelte` — 分类筛选、路径展示、别名展示优化
- `backend/tests/test_doc_version.py` — 覆盖 `doc_output`、类型归一、名称归一、历史兼容等验证场景
