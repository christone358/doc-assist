## 1. 统一正式版本存储根目录

- [ ] 1.1 在 `backend/doc_version_service.py` 中将正式版本的官方根目录收敛为仓库根目录下的 `doc_output/`
- [ ] 1.2 统一 `save_document`、`list_documents`、`list_versions`、`load_latest` 的路径计算逻辑，避免保存与查询分叉
- [ ] 1.3 保留对 `backend/docs/`、`docs/` 的读取兼容，但禁止新版本继续写入旧目录

## 2. 建立 canonical 文档类型体系

- [ ] 2.1 定义 canonical 文档类型集合：`requirements`、`design`、`test-plan`、`user-manual`、`api`、`general`
- [ ] 2.2 建立类型别名映射，统一处理 `req` / `test` / `user-guide` 等历史或口语输入
- [ ] 2.3 同步后端接口与前端筛选项，确保列表展示与保存规则使用同一套类型值

## 3. 建立文档系列名称归一机制

- [ ] 3.1 为需求规格、设计方案、测试方案、用户手册等文档定义标题后缀剥离规则
- [ ] 3.2 为模块、类、包、系统、服务、组件等对象定义轻量名称规整规则
- [ ] 3.3 为每个文档系列引入 alias 元数据，保存 canonical 名称与历史别名
- [ ] 3.4 在保存和查询时复用同一套“精确匹配 + 包含匹配 + 轻量模糊匹配”规则

## 4. 打通保存、加载与写作状态

- [ ] 4.1 调整 `save-draft`，保存成功后将 `writing_state.module_name`、`writing_state.doc_type` 回写为 canonical 值
- [ ] 4.2 调整 `load_saved_document`，加载历史文档后将 canonical `doc_name` 传递给后续写作链路
- [ ] 4.3 确保 `load_saved_document` 与正式保存使用同一文档系列解析规则

## 5. 优化 Web UI 文档管理展示

- [ ] 5.1 更新 `Documents.svelte`，按 canonical 文档类型筛选并展示中文标签
- [ ] 5.2 展示真实保存路径、最新版本、日期，以及 alias 信息
- [ ] 5.3 更新文档接口调用，确保 `doc_type` / `doc_name` 在 URL 中进行安全编码

## 6. 验证与一致性检查

- [ ] 6.1 增加测试：验证“保存为正式版本”实际落在 `doc_output/`
- [ ] 6.2 增加测试：验证 `test` / `test-plan`、`user-guide` / `user-manual` 等别名会归一到同一类型
- [ ] 6.3 增加测试：验证同一对象的多种命名可归入同一文档系列，并被 `load_latest` / `list_versions` 正确识别
- [ ] 6.4 检查 proposal、design、tasks 与 spec delta 是否使用同一组 root、canonical 类型和名称归一规则
