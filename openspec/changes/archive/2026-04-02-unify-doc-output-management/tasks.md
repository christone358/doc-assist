## 1. 统一正式文档来源为 `doc_output`

- [x] 1.1 识别 `backend/docs/` 下的 legacy 正式输出目录，并与 `backend/docs/conversations/` 会话数据目录区分
- [x] 1.2 将 legacy 正式输出迁移到 `doc_output/`，保留原有版本链信息
- [x] 1.3 收敛 `backend/doc_version_service.py` 的正式文档保存与查询逻辑，仅以 `doc_output/` 为正式来源
- [x] 1.4 移除或停用 `backend/docs/` 作为正式文档读取来源的逻辑，并明确保留 `backend/docs/conversations/`

## 2. 调整 Agent 历史正式版本读取链路

- [x] 2.1 修改历史文档发现工具，仅返回 `doc_output/` 中的正式文档
- [x] 2.2 修改历史文档加载工具，仅从 `doc_output/` 读取正式版本作为写作输入
- [x] 2.3 校验修改/续写场景中，Agent 不再把 `backend/docs/` 中的 legacy 输出作为输入来源

## 3. 扩展文档检索接口与结果管理页面

- [x] 3.1 扩展文档列表查询接口，支持按 `doc_type` 和模块关键字过滤 / 搜索
- [x] 3.2 让模块过滤 / 搜索匹配 canonical 模块名及别名
- [x] 3.3 更新 `Documents.svelte`，按实际输出的 canonical 文档类型进行分类筛选和展示
- [x] 3.4 确保页面展示的路径统一指向 `doc_output/` 下的正式输出路径
- [x] 3.5 排除 `backend/docs/` legacy 输出在文档结果管理页中的展示
- [x] 3.6 在 `requirements` 与 `user-manual` 类型下增加模块过滤和搜索控件
- [x] 3.7 校验页面的模块过滤 / 搜索通过后端查询接口生效，而不是仅基于当前前端结果集做本地筛选

## 4. 清理 backend 中的 legacy 输出文档

- [x] 4.1 删除已完成迁移的 `backend/docs/` legacy 正式输出文档目录
- [x] 4.2 验证清理后不会影响 `backend/docs/conversations/` 的读写

## 5. 验证与收口

- [x] 5.1 增加/更新测试：正式保存后路径位于 `doc_output/`
- [x] 5.2 增加/更新测试：legacy 正式输出迁移后可在 `doc_output/` 下被查询和加载
- [x] 5.3 增加/更新测试：文档结果管理页只展示 `doc_output/` 正式输出
- [x] 5.4 增加/更新测试：Agent 历史正式版本读取仅来自 `doc_output/`
- [x] 5.5 增加/更新测试：`requirements` / `user-manual` 页面支持按模块过滤和搜索
- [x] 5.6 执行 proposal、design、specs、tasks 一致性检查，确认“正式文档唯一来源 = `doc_output/`”在各 artifact 中保持一致
