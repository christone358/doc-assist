## Context

当前系统对 Skill 目录的运行时使用只完成了一半：

- `execute_skill` 会读取 `SKILL.md` 正文，并继续通过 `_extract_and_load_skill_tools()` 从正文中提取“专属工具文件”做动态 import；
- 但 `references/`、`reference/`、`templates/`、JSON 配置文件等静态资源不会自动进入运行时上下文；
- `write_document` 的最终写作调用只会再次读取 `SKILL.md` 正文和已收集事实，无法消费 Skill 在执行中显式引用的参考资料；
- 对于 `.py` 文件，目前只有“作为工具模块被导入”这一条路径，缺少“作为一次性脚本在 Skill 执行中被调用”的统一机制。

这导致 Skill 作者虽然已经按照 Claude/OpenCode 风格把规则、模板、检查清单和脚本放进 Skill 目录，但宿主运行时无法像官方 Skill 系统一样在需要时访问这些资源。

## Goals / Non-Goals

**Goals:**

- 为当前 Skill 执行链路提供 Skill 本地资源的运行时访问能力，覆盖文本参考资料和 Python 脚本两类核心场景
- 让 Skill Sub-agent 可以在执行时按 `SKILL.md` 的指引读取本地参考文件，并将结果显式传递给后续写作步骤
- 为 Skill 脚本提供统一执行入口，支持在当前 Skill 根目录下安全运行并返回结果
- 收敛资源访问的安全边界，避免路径穿越、越权读取和无界脚本执行
- 保持与现有“Skill 专属工具动态导入”机制兼容，不破坏已有 Skill

**Non-Goals:**

- 不在本次变更中实现任意二进制资源预览、图片解析或大型文件流式处理
- 不把所有 `references/` 自动无差别塞进 prompt；资源是否读取仍由 Skill 执行逻辑决定
- 不替换现有 `_extract_and_load_skill_tools()` 机制；已有工具模块加载逻辑继续保留
- 不在本次变更中扩展到 shell 脚本、Node 脚本等多语言执行器；第一阶段只覆盖 Python 脚本

## Decisions

### Decision 1: 通过专用运行时工具暴露 Skill 本地资源，而不是做隐式全量扫描注入

系统新增两类 Skill 运行时工具：

- `read_skill_resource(relative_path)`：读取当前 Skill 根目录下的本地文本资源
- `run_skill_script(relative_path, payload?)`：在当前 Skill 根目录下执行 Python 脚本，并返回 stdout 结果

选择“显式工具调用”而不是“自动扫描并全量注入 prompt”，原因是：

- 更接近 Claude/OpenCode 的使用体验：`SKILL.md` 先定义何时需要哪些资源，Agent 在执行时按需读取
- 能控制 prompt 体积，避免把整个 `references/` 目录无差别塞进上下文
- 资源读取与脚本执行都会留下明确的工具调用记录，便于日志和问题排查

备选方案：

- 后端在进入 Skill 时预加载所有 `references/`：实现简单，但会放大 prompt、弱化 Skill 作者的按需设计
- 只提供文件读取，不提供脚本执行：不能覆盖官方 Skill 中常见的 `scripts/*.py` 场景

### Decision 2: 资源访问严格绑定“当前 Skill 根目录”，并通过统一路径解析器做安全校验

所有 Skill 资源访问都必须通过统一的 `_resolve_skill_resource_path(skill_dir, relative_path)`：

- 路径必须是相对路径
- 归一化后必须仍位于当前 Skill 根目录内
- 默认拒绝隐藏文件、`__pycache__`、`.pyc`、超大文件和不可解码文本
- `run_skill_script` 仅允许执行 `.py` 文件

这样可以把安全边界落实到宿主系统，而不是交给 `SKILL.md` 自觉约束。

备选方案：

- 直接允许绝对路径：会让 Skill 越权访问宿主文件系统
- 只做字符串前缀判断：无法有效防御 `..`、符号链接等路径绕过

### Decision 3: 已加载的 Skill 资源写入共享 ConversationContext，并由后续工具显式消费

新增 `ConversationContext.loaded_skill_resource_parts`（或等价字段），保存本轮已读取的 Skill 资源正文与脚本输出摘要。格式上保留来源标签，例如：

```text
### [Skill 参考资料: references/structure/module-manual.md]
...

### [Skill 脚本输出: scripts/extract_outline.py]
...
```

这样设计有两个好处：

- `read_skill_resource` / `run_skill_script` 与 `write_document` 之间通过共享上下文衔接，不需要把前一阶段的结果塞回用户消息
- 后续若还有其他生成类工具，也可以复用同一份已加载资源，而不是重新读取

备选方案：

- 让工具只返回文本，不写共享上下文：最终写作调用看不到前面已读取的资源
- 为每类资源单独建新的持久化存储：本轮执行数据没有必要落盘，复杂度过高

### Decision 4: `write_document` 只保留最小不变约束，并显式注入已加载 Skill 资源

`write_document` 的系统提示保持最小边界：

- 使用中文
- 严格基于提供上下文
- 只输出正文，不输出过程总结/元信息

Skill 的结构规范、局部修订规则、检查要求不再由通用提示重复声明，而是通过两部分进入上下文：

1. `SKILL.md` 正文
2. `loaded_skill_resource_parts`

这样可以避免通用提示稀释 Skill 自身约束，也能让 Skill 中的 `references/*.md` 真正参与最终写作。

备选方案：

- 继续在 `write_document` 中堆通用规则：会与 Skill 自定义结构发生冲突
- 只让 Sub-agent 自己“看过”参考资料，不传给 `write_document`：最终生成模型仍然无法遵守这些约束

### Decision 5: Python Skill 脚本采用子进程执行约定，而不是 import 后反射调用

对于一次性 Skill 脚本，`run_skill_script` 使用子进程运行：

- 命令形态为 `python3 <script_path>`
- `cwd` 设为当前 Skill 根目录
- 可选 `payload` 通过 stdin 传入 JSON 字符串
- stdout 作为脚本返回结果，stderr 进入错误日志
- 配置超时和输出大小上限

保留现有 `_extract_and_load_skill_tools()` 继续处理“注册为工具函数”的 Python 模块；新增脚本执行能力则专门服务“不是工具、但需要运行”的脚本资源。

备选方案：

- 全部改成 import 并直接调用：要求所有脚本遵循固定函数签名，耦合更高，也更难隔离副作用
- 允许任意 shell 命令：攻击面过大，不适合第一阶段

## Risks / Trade-offs

- [Risk] Skill 作者可能在 `SKILL.md` 中引用不存在的资源路径 → Mitigation：工具返回明确错误，日志中记录缺失路径，Sub-agent 可继续推理或降级处理
- [Risk] 脚本执行可能变慢或卡死 → Mitigation：对子进程设置超时、stdout 大小上限，并将 stderr 摘要回传
- [Risk] 参考资料被重复读取导致 prompt 膨胀 → Mitigation：按路径去重写入 `loaded_skill_resource_parts`，并限制单文件大小
- [Risk] 旧 Skill 不知道这些新工具的存在 → Mitigation：保持向后兼容；只有在 `SKILL.md` 主动引用时才会使用
- [Risk] 资源读取结果污染下一轮 → Mitigation：`loaded_skill_resource_parts` 作为 per-round 字段，在每轮 `ConversationContext` 创建时清空

## Migration Plan

1. 为 `ConversationContext` 增加本轮 Skill 资源缓存字段与必要的辅助元数据
2. 新增 Skill 资源运行时工具模块，实现路径校验、文本读取、脚本执行和结果记录
3. 在 `execute_skill` 创建 Sub-agent 时注册这些工具，并在固定执行规范中说明用途与边界
4. 调整 `write_document`，把已加载 Skill 资源与事实信息一并注入最终写作 prompt
5. 为至少一个现有 Skill（如 `user-manual-writter`）补充真实使用路径，验证 `references/*.md` 能影响最终输出
6. 增加单元测试/集成测试，覆盖路径越权、缺失文件、脚本超时、资源注入成功等关键分支

回滚策略：

- 若资源工具引入异常，可先从 Sub-agent 工具列表中移除新工具，并恢复 `write_document` 只使用 `SKILL.md` + 事实信息
- 新增字段为 per-round 内存字段，不涉及数据库迁移，代码回滚即可恢复旧行为

## Open Questions

- 是否需要在后续阶段支持 `templates/` 的结构化渲染工具，而不仅仅是按文本读取；本次先按普通资源文件处理
- 是否需要为 JSON 资源提供“解析后返回结构化对象”的专用工具；本次先返回文本结果，由模型自行消费
- 是否需要把 `validation_only`、`required_before_write` 这类声明机制做成结构化约定；本次先以 Skill 自然语言指引 + 显式工具调用为主
