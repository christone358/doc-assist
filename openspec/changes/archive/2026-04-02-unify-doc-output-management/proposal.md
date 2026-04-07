## Why

当前正式文档输出同时散落在 `doc_output/` 与 `backend/docs/` 等多个目录，文档结果管理页面展示的分类也未完全对齐实际输出类型，导致用户难以稳定管理结果，Agent 读取历史正式版本时也缺少单一可信来源。

现在需要把 `doc_output/` 收敛为正式文档的唯一来源，同时让前端文档管理页按实际输出类型管理文档，并确保 Agent 仅从 `doc_output/` 读取历史正式版本作为写作输入。

## What Changes

- 统一正式文档输出根目录为仓库根目录下的 `doc_output/`
- **BREAKING** 停止在 `backend/docs/` 下保留或继续写入正式输出文档；现有 legacy 正式输出需先迁移到 `doc_output/`，再清理旧目录
- 修改文档管理页面，使其按实际输出的 canonical 文档类型分类管理和展示结果
- 在需求规格、用户手册类型下，支持按模块进行过滤和搜索
- 修改 Agent 历史正式版本读取策略，写作时仅从 `doc_output/` 发现和加载历史正式版本
- 统一保存、查询、加载和前端展示的文档路径口径，消除多目录并存带来的歧义

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `document-version-management`: 正式文档输出目录、查询目录和历史版本来源统一为 `doc_output/`
- `web-ui`: 文档结果管理页面按实际输出文档类型分类展示，并展示 `doc_output/` 下的真实路径；在需求规格、用户手册中支持模块过滤和搜索
- `agent-core`: Agent 在修改/续写场景中仅从 `doc_output/` 读取历史正式版本作为写作输入
- `saved-document-access`: 历史文档发现与加载工具仅返回并加载 `doc_output/` 中管理的正式版本

## Impact

- `backend/doc_version_service.py`
- `backend/main.py`
- `backend/agent/adk/saved_doc_tools.py`
- `backend/agent/adk/write_document_tool.py` 或相关写作链路
- `frontend/src/lib/components/Documents.svelte`
- `frontend/src/lib/api.js`
- 文档列表查询接口的模块过滤 / 搜索参数
- `backend/docs/` 下的历史正式输出文档清理策略
- 相关文档版本管理与页面展示测试
