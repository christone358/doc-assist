# MCP 统一运行时访问协议设计

## 文档信息
- 文档名称: MCP 统一运行时访问协议设计
- 版本: v1.0.0
- 创建日期: 2026-04-02
- 作者: Codex
- 适用范围: NextAgent Doc Assistant 主 Agent、写作 Skill、项目事实库、Skill 本地资源与历史文档访问

## 1. 背景

当前项目已经形成了较清晰的分层形态：

- 主 Agent 负责用户意图理解、任务拆解、Skill 选择与全局对话管理
- 写作 Skill 负责具体文档写作与局部推理
- 项目事实信息库负责提供模块、用例、API、原型、代码等事实依据
- 历史文档负责保存已生成产物及其版本

但运行时访问链路仍然分散：

- 项目事实信息主要通过宿主内置工具访问
- Skill 目录中的 `references/`、`templates/`、`scripts/` 等资源缺少统一运行时入口
- 历史文档访问与事实访问、Skill 资源访问采用不同思路
- 主 Agent 与 Skill Sub-agent 在“可访问什么资源、通过什么接口访问”上存在不一致

因此需要引入统一的运行时访问协议。本文建议采用 MCP 作为统一访问机制。

## 2. 设计目标

### 2.1 目标

- 为主 Agent 和 Skill Sub-agent 提供统一的运行时访问协议
- 统一项目事实、Skill 本地资源、历史文档的访问入口风格
- 保持不同资源域的语义边界、权限边界和返回结构清晰
- 让 Skill 中声明的参考资料、模板和脚本能够在运行时按需访问
- 为后续能力扩展提供稳定适配层，降低宿主框架耦合

### 2.2 非目标

- 本期不要求把所有现有工具一次性迁移完成
- 本期不把 Skill 调度本身强制改造成 MCP 调用
- 本期不将所有资源抽象为一个万能 `read_resource` 接口
- 本期不改变主 Agent 负责编排、Skill 负责写作的职责划分

## 3. 核心结论

### 3.1 统一协议，不统一成一个万能抽象

统一的是访问机制、调用风格、日志审计、错误处理与鉴权方式。

不统一的是领域语义、参数模型、权限边界、返回结构与缓存策略。

因此，项目事实、Skill 本地资源、历史文档虽然都通过 MCP 暴露，但应保留不同 namespace / capability，而不是压平成一个“万能资源读取器”。

### 3.2 主 Agent 是编排中枢，MCP 是统一访问层

主 Agent 的职责仍然是：

- 理解用户意图
- 决定是直接答复还是调度 Skill
- 管理多轮对话状态和执行摘要

MCP 的职责是：

- 提供统一、标准化的资源访问入口
- 隔离底层事实库、文件系统、文档存储的具体实现
- 为主 Agent 与 Skill Sub-agent 提供一致的可调用能力面

### 3.3 Skill 调度与 Skill 内部资源访问是两层问题

这是实现中必须明确区分的边界：

- `Skill 调用`：指主 Agent 选择哪个 Skill，并触发哪个 Sub-agent 执行
- `Skill 内部资源访问`：指 Skill 在执行过程中，如何读取自己的参考资料、模板、脚本、事实信息和历史基线稿

结论如下：

- 主 Agent 对 Skill 的调度，不一定必须通过 MCP
- Skill 在执行过程中对项目事实、Skill 本地资源、历史文档的访问，建议统一通过 MCP

## 4. 推荐总体架构

```text
用户
  |
  v
主 Agent / Orchestrator
  |- 意图理解
  |- 任务拆解
  |- Skill 选择
  |- 全局摘要与状态管理
  |
  +----> MCP Runtime Layer
           |- facts.*
           |- skill.*
           |- docs.*
           |- future: templates.* / code.*
                  |
                  v
             项目事实库 / Skill 本地资源 / 历史文档存储
  |
  v
写作 Skill Sub-agent
  |- 写作推理
  |- 按需取数
  |- 正文生成
  |- 执行摘要返回
  |
  +----> 同一个 MCP Runtime Layer
```

## 5. 为什么不能混成一个抽象

### 5.1 三类资源的本质不同

#### 项目事实 `facts`

- 面向工程事实查询
- 典型对象是模块、用例、功能点、API、原型、代码
- 查询入口通常是模块标识、事实类型、领域对象

#### Skill 本地资源 `skill`

- 面向当前 Skill 私有运行时资源
- 典型对象是 `references/`、`templates/`、`scripts/`、`rules/`、`checklists/`
- 查询入口通常是相对 Skill 根目录的路径

#### 历史文档 `docs`

- 面向项目产物和版本基线
- 典型对象是需求文档、设计文档、用户手册等历史版本
- 查询入口通常是 `doc_type + doc_name + version`

这三类资源虽然都属于“运行时上下文来源”，但不是同一种领域对象。

### 5.2 工具语义必须让 Agent 容易使用

如果把所有能力压成一个万能接口，例如：

```text
read_resource(path_or_id, type?, scope?, mode?)
```

那么模型需要自己猜：

- 当前要访问的是 facts、skill 还是 docs
- 参数传模块名、文件路径还是文档名
- 应返回全文、摘要、元数据还是版本信息

这会显著增加模型的工具选择和参数推理负担。

而按 namespace 划分后，工具语义更稳定：

```text
facts.get_module("业务系统管理")
docs.load_saved("user-manual", "业务系统管理模块")
skill.read_resource("references/structure/module-manual.md")
skill.run_script("scripts/extract_outline.py", payload)
```

### 5.3 权限边界不同

#### `facts.*`

- 面向项目公共事实
- 主 Agent 和 Skill 通常都可访问
- 风险相对较低

#### `skill.*`

- 仅允许当前 Skill 访问自己的根目录资源
- 涉及脚本执行时风险最高
- 不能跨 Skill、不能越出 Skill 根目录

#### `docs.*`

- 面向项目产物和版本内容
- 需要和当前项目、文档类型、版本语义绑定
- 访问策略与 `facts.*`、`skill.*` 不同

### 5.4 返回结构和缓存策略不同

`facts.*` 更适合实体型、结构化返回。  
`skill.*` 更适合资源型、路径型返回。  
`docs.*` 更适合版本型、基线型返回。

同样，缓存策略也不同：

- `facts.*` 适合模块级事实缓存
- `skill.*` 适合当前执行轮次内资源缓存
- `docs.*` 适合基线稿和版本元数据缓存

因此统一协议时，应统一“风格”和“治理”，而不是统一“领域模型”。

## 6. 推荐 namespace 设计

### 6.1 `facts.*`

用于项目事实查询。

当前第一阶段只保留和现有 facts 治理模型一致的两个 public 工具：

- `facts.list_modules()`
- `facts.get_module(module_ref)`

这样设计的原因是：当前 facts 的稳定维护单元仍然是“模块聚合根”，真实主路径只有：

- 查询有哪些模块
- 读取某个模块聚合根下的全部信息

模块引用解析、generated JSON / Markdown 视图选择等逻辑仍可在 server 内部存在，但不作为第一阶段对外 public 工具契约。

### 6.2 `skill.*`

用于当前 Skill 私有资源访问。

第一阶段能力：

- `skill.list_resources()`
- `skill.read_resource(relative_path)`
- `skill.run_script(relative_path, payload?)`

这里的 `skill.*` 默认绑定“当前执行中的 Skill 上下文”，不建议让模型显式传入任意 `skill_id`。

同时，这组能力在第一阶段按**内部受控工具集**实现：

- `facts.*`、`docs.*` 作为公共工具集，按 remote MCP server 能力对外暴露
- `skill.*` 作为内部工具集，优先服务当前系统内的 Skill Sub-agent
- 其中 `skill.run_script` 风险最高，默认仅内部可用

### 6.3 `docs.*`

用于历史文档访问。

第一阶段能力：

- `docs.list_saved(doc_type?)`
- `docs.load_saved(doc_type, doc_name, version?)`

这里要特别区分两类内容：

- **已保存正式文档**：通过 `docs.*` 读取
- **当前对话未保存草稿**：不通过 `docs.*` 暴露，仍属于会话态上下文 / working draft

也就是说，`docs.*` 在第一阶段只承载“正式版本语义”，不混入未保存草稿。

### 6.4 Server 形态与技术栈

本次实现按标准 remote MCP server 方式设计，技术栈选择如下：

- 语言与运行时：Python 3.11
- SDK：官方 Python MCP SDK
- Server 组织方式：FastMCP
- 传输模式：
  - 本地调试：`stdio`
  - remote 接入：`Streamable HTTP`

部署边界如下：

- MCP server 在理论上应可独立启动和运行
- 当前项目阶段允许与主系统一起打包部署
- 即使与主系统同进程或同部署单元运行，也要保持独立入口、标准传输和宿主无关的 public 工具契约

## 7. Skill 调用是否通过 MCP

### 7.1 推荐结论

`Skill 调度` 本身不必强制走 MCP。

原因如下：

- Skill 调度属于编排层职责，归主 Agent / Orchestrator 所有
- 当前系统已经有较明确的 `execute_skill` 调用链
- Skill 选择需要结合对话状态、任务规划、失败恢复和执行摘要，这些更像宿主运行时职责，而不是外部资源访问职责

因此更推荐：

- 主 Agent 继续通过宿主运行时直接调度 Skill Sub-agent
- 被调度的 Skill 在执行过程中，通过 MCP 访问 facts、skill resources、docs

### 7.2 什么情况下 Skill 调度也可以走 MCP

如果后续希望做到：

- Skill 动态发现更彻底
- 不同 Skill Executor 可插拔
- Orchestrator 与 Skill Runtime 完全解耦

那么未来可以再抽象出：

- `skills.list_capabilities()`
- `skills.invoke(skill_id, payload)`

但这应视为下一阶段能力，而不是当前第一阶段必须做的内容。

## 8. Skill 下内部资源的使用，是否通过 MCP

### 8.1 推荐结论

是。  

Skill 下内部资源的使用，建议统一通过 MCP 暴露和访问。

包括但不限于：

- `references/*.md`
- `templates/*.md`
- `scripts/*.py`
- `rules/*.md`
- `checklists/*.md`
- 未来可能存在的 JSON 配置文件

### 8.2 原因

原因有四个：

1. 保证主 Agent、Skill Sub-agent 看到的是同一套标准能力面
2. 避免 Skill 资源访问继续依赖宿主中的零散硬编码
3. 方便记录资源读取和脚本执行的日志、审计和错误信息
4. 便于控制安全边界，只允许访问当前 Skill 根目录

### 8.3 使用方式

Skill 不需要直接知道底层文件系统细节，只需知道自己可以调用：

- `skill.read_resource("references/structure/module-manual.md")`
- `skill.read_resource("references/rules/writing-rules.md")`
- `skill.read_resource("references/checklists/quality-checklist.md")`
- `skill.run_script("scripts/extract_outline.py", payload)`

MCP 负责：

- 校验路径是否在当前 Skill 根目录下
- 控制隐藏文件、超大文件、非法扩展名
- 执行 Python 脚本并返回标准结果
- 将成功读取的结果记录到当前执行上下文

## 9. 统一后的职责边界

### 9.1 主 Agent / Orchestrator

- 接收用户意图
- 决定直接答复还是调度 Skill
- 管理多轮对话摘要、任务状态、执行历史
- 不负责硬编码 facts / skill resources / docs 的底层读取逻辑

### 9.2 Skill Sub-agent

- 接收主 Agent 委派的具体写作目标
- 决定本轮按什么顺序取数
- 通过 MCP 访问事实、Skill 资源、历史文档
- 生成正文并返回执行摘要

### 9.3 MCP Runtime Layer

- 对 facts / skill / docs 暴露稳定 namespace
- 屏蔽底层目录结构与存储实现
- 执行权限校验、边界控制、日志记录、错误归一化

## 10. 分阶段落地建议

### 第一阶段

- 保持现有 `execute_skill` 作为 Skill 调度入口
- 将现有 `fact_tools` 适配为 `facts.*` MCP 能力
- 将 Skill 资源访问能力落到 `skill.*`
- 将历史文档访问能力落到 `docs.*`

### 第二阶段

- 在运行时上下文中统一记录三类来源：
  - facts loaded
  - skill resources loaded
  - docs base loaded
- 让最终写作 prompt 注入三类来源，而非只注入 facts

### 第三阶段

- 视需要再考虑 Skill 调度本身是否也抽象为 MCP 能力
- 建立更强的 capability registry 和动态发现机制

## 11. 最终结论

本项目应采用“统一访问协议 + 保留领域 namespace”的 MCP 设计，而不是“一个万能资源工具”。

明确结论如下：

- 主 Agent 和 Skill Sub-agent 对资源访问，建议统一通过 MCP
- 项目事实、Skill 本地资源、历史文档应保留不同 namespace / capability
- Skill 调度本身不必在第一阶段就改造成 MCP
- Skill 内部资源的读取和脚本执行，建议统一通过 MCP

可以概括为一句话：

> MCP 统一的是访问门面，不是抹平领域边界。
