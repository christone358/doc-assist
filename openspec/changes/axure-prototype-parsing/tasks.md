## 1. 原型包解析器骨架

- [x] 1.1 新建 `backend/prototype_parser/` 模块目录和基础数据模型
- [x] 1.2 实现原型包扫描器，识别 `project-facts/prototypes/` 下的 Axure 原型包、入口页和页面文件清单
- [x] 1.3 定义并落地 `PrototypePackageManifest`、`PrototypePageIndexItem`、`PrototypePageFact` 数据结构

## 2. 页面解析与摘要生成

- [x] 2.1 实现 HTML 读取与规范化逻辑，提取页面标题和可见文本
- [x] 2.2 实现 DOM 元素提取逻辑，输出按钮、输入框、表格、选项卡、对话框和链接
- [x] 2.3 实现布局分区与用户可见消息提取逻辑
- [x] 2.4 实现 Axure 交互增强提取，输出页面跳转、热点触发、弹层或主要交互摘要
- [x] 2.5 实现 `summary_builder`，为单页解析结果生成 `llm_summary`

## 3. 派生产物与增量刷新

- [x] 3.1 设计并实现派生产物目录结构，生成包索引、页面索引和单页事实 JSON 文件
- [x] 3.2 实现页面索引与单页事实仓库读取接口，屏蔽底层 JSON 文件细节
- [x] 3.3 实现原型包变更检测与指纹计算机制
- [x] 3.4 实现增量刷新流程，确保查询前派生产物可自动更新

## 4. 模块档案与上下文加载集成

- [x] 4.1 调整项目事实派生流程，使模块档案页面名称与派生页面索引建立稳定匹配关系
- [x] 4.2 更新原型摘要加载逻辑，使模块事实返回模块关联页面摘要而不是原始 HTML
- [x] 4.3 在上下文加载状态输出中加入页面原型加载摘要、匹配状态和页面数量信息

## 5. MCP 原型工具开发

- [x] 5.1 在 `backend/mcp_runtime/` 中新增 `prototypes_namespace.py`
- [x] 5.2 实现 `prototypes.list_pages(module_ref)`，返回模块关联页面列表和 `llm_summary`
- [x] 5.3 实现 `prototypes.get_page(page_ref)`，返回结构化页面事实、`llm_summary`、来源路径和解析告警
- [x] 5.4 定义原型 namespace 的错误类型和错误转换逻辑
- [x] 5.5 在 MCP server 注册表中注册 `prototypes.*` 公共工具

## 6. Agent / Skill 运行时接入

- [x] 6.1 在 `agent/adk/mcp_tools.py` 中新增 `prototypes.*` 包装函数
- [x] 6.2 在主 Agent 工具集里开放 `prototypes.*` MCP 工具
- [x] 6.3 在 Skill 执行链路中开放 `prototypes.*` MCP 工具给需要写作的 Skill
- [x] 6.4 将 `prototypes.get_page` 返回的 `llm_summary` 和必要事实片段写入当前轮次上下文
- [x] 6.5 更新 `write-user-manual` 等相关写作 Skill 说明，明确通过 MCP 原型工具优先使用页面事实并保留待确认标记

## 7. 测试与样例验证

- [x] 7.1 为原型包扫描器补充单元测试
- [x] 7.2 为 DOM 提取、Axure 交互提取和 `llm_summary` 生成补充单元测试
- [x] 7.3 为派生产物仓库、指纹计算和增量刷新补充单元测试
- [x] 7.4 为 `prototypes.*` MCP 工具补充集成测试
- [x] 7.5 为 Agent / Skill 上下文接入链路补充集成测试
- [ ] 7.6 使用一个完整 Axure 导出样例验证用户手册写作链路，确认能引用真实页面要素、交互和来源信息
