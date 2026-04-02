## Why

当前 Skill 运行时只稳定加载 `SKILL.md` 正文，`references/`、`scripts/`、`templates/` 以及其他本地资源虽然存在于 Skill 目录中，但 Agent 与写作执行链路无法可靠访问它们。这使得 Skill 设计只能停留在“文档约定”层，关键结构规则、参考资料和辅助脚本无法在运行时真正生效，导致输出结果与 Skill 约束脱节。

## What Changes

- 为 Skill 执行链路增加对 Skill 目录内本地资源的运行时访问能力，覆盖 Markdown、JSON、Python 及其他受支持文件类型。
- 为执行中的 Skill Sub-agent 提供受限的资源读取与脚本执行入口，访问范围限定在当前 Skill 根目录内。
- 建立“已加载 Skill 资源”在执行上下文中的持久传递机制，确保后续写作或生成步骤能够消费前面读取的参考资料。
- 调整 `write_document` 的集成方式，使其能够消费 Skill 在当前轮次中显式加载的参考内容，而不是只依赖 `SKILL.md`。
- 明确资源访问的安全边界、路径校验、结果记录和可观测性要求，避免任意文件访问或脚本滥用。

## Capabilities

### New Capabilities

- `skill-resource-runtime-access`: 定义 Skill 目录内资源在执行期的读取、执行、上下文传递与安全约束。

### Modified Capabilities

- `skill-framework`: 扩展 Skill 目录资源的正式契约，明确哪些本地资源可在运行时被 Skill 使用，以及 Skill 如何声明这些资源。
- `agent-core`: 扩展 Agent/Skill 执行工作流，使 Skill Sub-agent 能在运行中访问本地资源并将结果传递给后续生成步骤。

## Impact

- 影响代码：`backend/agent/adk/execute_skill_tool.py`、`backend/agent/adk/write_document_tool.py`、`backend/agent/adk/document_agent.py`、Skill 加载/解析相关模块，以及可能新增的 Skill 资源工具实现。
- 影响 Skill 运行契约：Skill 作者可以在 `SKILL.md` 中规划 `references/`、`scripts/` 等资源的使用时机，但宿主系统需要真正实现对应能力。
- 影响安全与审计：需要增加路径约束、资源大小控制、脚本执行白名单或显式边界，并记录资源读取/执行行为。
