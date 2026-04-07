## 1. MCP Runtime 抽象与上下文模型

- [x] 1.1 新增 MCP runtime 抽象层，定义 `facts.*`、`skill.*`、`docs.*` 三个 namespace 的接口、工具清单、标准返回结果和统一错误结构
- [x] 1.2 调整主 Agent 与子 Agent 的上下文模型：主 Agent 仅保留委派所需 handoff 信息，子 Agent 在独立 working context 中按来源记录 facts、skill resources、docs 的已加载内容
- [x] 1.3 为 MCP runtime 增加统一日志与审计辅助逻辑，记录 namespace、目标标识、结果状态和错误摘要

## 2. MCP Server 技术栈与基础设施

- [x] 2.1 在后端依赖中引入官方 Python MCP SDK，并固定与当前 Python 3.11 兼容的版本范围
- [x] 2.2 基于官方 Python SDK 和 `FastMCP` 搭建 MCP server 基础骨架，明确 server 入口、注册方式和生命周期
- [x] 2.3 规划并实现两种传输模式：本地调试使用 `stdio`，正式接入优先使用 `Streamable HTTP`
- [x] 2.4 为 MCP server 增加基础运行配置，明确当前可与主系统打包运行，但保留独立启动入口与独立部署能力
- [x] 2.5 按 remote MCP server 方式设计 server 启动与部署结构，避免退化为仅能在应用内调用的 adapter

## 3. 公共工具集 vs 内部工具集拆分

- [x] 3.1 明确公共工具集范围，至少包括 `facts.list_modules`、`facts.get_module` 与 `docs.*` 核心工具
- [x] 3.2 明确内部工具集范围：`skill.list_resources`、`skill.read_resource`、`skill.run_script` 第一阶段均为内部受控能力，不作为 public remote tools 暴露
- [x] 3.3 在 MCP server 注册层实现公共工具与内部工具的分组注册或配置化开关
- [x] 3.4 为公共工具集补充宿主无关的 schema 校验，避免暴露内部状态对象语义或依赖隐式宿主上下文

## 4. `facts.*` Namespace 接入

- [x] 4.1 基于现有模块索引 / `generated/views/modules.md` 实现 `facts.list_modules()` adapter，并对齐结果格式
- [x] 4.2 基于现有 `load_module_fact_sheet` 与模块引用解析辅助逻辑实现 `facts.get_module(module_ref)` adapter，并对齐结果格式
- [x] 4.3 统一 `facts.get_module` 在服务端内部的模块引用解析、generated 视图优先级和回退策略
- [x] 4.4 为 `facts.*` adapter 明确只读约束，拒绝写操作并返回统一错误结果
- [x] 4.5 明确 `facts.*` 第一阶段不暴露更细粒度 public 工具

## 5. `docs.*` Namespace 接入

- [x] 5.1 基于现有 `list_saved_documents` 实现 `docs.list_saved(doc_type?)` adapter，并对齐结果格式
- [x] 5.2 基于现有 `load_saved_document` 实现 `docs.load_saved(doc_type, doc_name, version?)` adapter，并对齐结果格式
- [x] 5.3 为 `docs.*` adapter 明确只读约束，拒绝写操作并返回统一错误结果
- [x] 5.4 明确 `docs.*` 第一阶段仅覆盖已保存正式文档，不将当前对话未保存草稿纳入 public MCP 工具契约

## 6. `skill.*` Namespace 实现

- [x] 6.1 基于当前 Skill 根目录实现 `skill.list_resources()`，暴露可读资源清单与资源分类信息
- [x] 6.2 实现 `skill.read_resource(relative_path)`，完成相对路径校验、文本读取、来源标记和上下文写入
- [x] 6.3 实现 `skill.run_script(relative_path, payload)`，完成 Python 脚本受限执行、超时控制、stdout 收集和错误摘要输出
- [x] 6.4 为 `skill.*` namespace 增加当前 Skill 根目录边界校验，拒绝跨 Skill、隐藏文件和不受支持类型
- [x] 6.5 按公共/内部工具集划分 `skill.*` 默认暴露策略，并确保 `skill.run_script` 默认仅内部可用

## 7. Agent / Skill 运行链路集成

- [x] 7.1 调整主 Agent 与 Skill Sub-agent 的工具注册方式，使运行时资源访问优先经由 MCP namespace 暴露
- [x] 7.2 对主 Agent 做最小必要适配：更新其可用公共工具声明与基础职责说明，使其在第一阶段即可识别并使用新的 MCP 公共工具名完成查询与委派
- [x] 7.3 保持 `execute_skill` 继续负责 Skill 调度、session 状态转移和执行摘要生成，不在本阶段把 Skill 调度改造成 MCP 调用
- [x] 7.4 调整 `write_document` 上下文构建逻辑，只注入子 Agent 当前 working context 中通过 MCP 已显式加载的 facts、skill resources 和 docs 基线内容，不直接复用主 Agent 完整上下文
- [x] 7.5 完成切换后移除不再符合新契约的旧工具路径和旧假设，避免主 Agent 继续依赖 legacy 工具模型
- [x] 7.6 保留未保存草稿为会话态 working draft：主 Agent 仅传递必要 handoff，子 Agent 从内部草稿状态读取并在写作结束后按现有会话机制更新

## 8. 验证、回归与文档

- [x] 8.1 为 `facts.*`、`skill.*`、`docs.*` namespace 增加自动化测试，覆盖成功、缺失、越权和错误归一化场景，重点验证 `facts.list_modules` 与 `facts.get_module`
- [x] 8.2 为 MCP server 增加 `stdio` 与 `Streamable HTTP` 两种模式的连通性验证与基础回归
- [x] 8.3 为公共工具集增加 remote 协议兼容性与基础互操作验证，确认其可被标准 MCP client 调用，但不在本阶段展开外部 client 产品开发
- [x] 8.4 为主 Agent 和 Skill Sub-agent 增加集成验证，确认两者都能通过统一 namespace 访问运行时资源、主 Agent 已切换到新的公共 MCP 工具名，并且主 Agent 只保留必要 handoff 信息而不读取子 Agent 完整 working context
- [x] 8.5 选取至少一个现有 Skill（如 `user-manual-writter`）做端到端回归，验证 Skill 参考资料与历史基线稿能够通过 MCP 影响最终写作结果
- [x] 8.6 增加“已保存正式文档 vs 未保存草稿”回归，确认前者通过 `docs.*` 加载，后者通过会话态草稿状态延续
- [x] 8.7 更新开发文档，说明 remote server 定位、技术栈选择、公共工具集/内部工具集边界、独立运行能力与当前打包部署策略、各自工具清单、Skill 调度与资源访问分层原则，以及“正式版本走 `docs.*`、未保存草稿走会话态上下文”的规则
