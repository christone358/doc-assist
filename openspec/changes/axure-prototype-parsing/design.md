## Context

当前系统已经支持将 Axure 导出的完整 HTML 原型包集中存放在 `project-facts/prototypes/` 下，并通过模块档案中的“页面 / 原型”章节维护模块关联页面名称。仓库内也已有基础页面扫描能力，会为 HTML 页面生成 `page-index.json` 一类的轻量索引，但这些派生结果只解决了“有哪些页面”，没有解决“页面上有什么”“页面之间如何跳转”“写作 Skill 如何稳定读取真实界面要素”。

现状的主要问题有三类：

1. `context_loader` 对 prototypes 的读取仍偏向原始内容，不适合直接作为用户手册、需求说明等文档写作上下文。
2. 模块与页面的对应关系是人工维护的，这是权威事实；但系统缺少基于这些页面名回查 Axure 原型包、提取结构化页面事实的能力。
3. 写作 Skill 虽然已经知道“原型可作为事实来源”，但缺少通过 MCP server 读取页面结构化要素的专门能力，因此无法可靠生成真实按钮、字段、表格列、提示语和交互路径。

本次设计要在不改变“模块档案是唯一人工维护事实源”这一前提下，引入系统级原型解析能力，并将其作为 MCP server 暴露给 Agent 与专项写作 Skill 按需调用。

本次交付将明确拆成两个开发对象：

1. **Axure 原型包解析器**
- 输入：`project-facts/prototypes/` 下的完整 Axure HTML 导出目录
- 输出：页面索引、sitemap、单页结构化页面事实、解析告警
- 责任：把原始 HTML 包转换成 LLM 可消费的中间表示

2. **`prototypes.*` MCP 工具**
- 输入：`module_ref`、`page_ref`、可选的 `package_ref`
- 输出：页面列表、单页详情、来源路径、证据与告警
- 责任：把解析结果稳定暴露给 Agent / Skill，而不是让调用方直接接触 HTML 或派生文件

## Goals / Non-Goals

**Goals:**
- 自动扫描 `project-facts/prototypes/` 下的 Axure 导出目录，识别页面、入口页和页面间关系。
- 为每个页面生成结构化页面事实，至少覆盖页面标题、布局分区、关键界面元素、可见文本和主要交互。
- 将解析结果沉淀为派生索引和页面事实缓存，供 Agent、Skill 和后续 UI 浏览能力复用。
- 为文档编写 Skill 和 Agent 提供稳定的 MCP 原型查询能力，使其可以按模块关联页面和页面详情读取原型事实。
- 保持模块档案中的页面名称列表仍是模块到页面关系的权威来源，系统只做解析与匹配，不反向改写人工事实。

**Non-Goals:**
- 不尝试 100% 还原 Axure 的所有动态行为、动画和复杂条件逻辑。
- 不在本次设计中实现原型在线预览或截图生成界面。
- 不要求用户手工维护额外的页面 ID、交互图或派生 JSON。
- 不把派生页面事实提升为与模块档案并列的权威事实源。

## Decisions

### 决策1：将原型解析做成系统级共享能力，并通过 MCP server 暴露

**选择**：在后端新增系统级原型解析能力，并通过 MCP server 暴露 `prototypes.*` namespace；ADK 层只负责把这些 MCP 工具包装给主 Agent 和 Skill Sub-agent 使用。

**理由**：
- Axure 解析是基础设施能力，不只服务用户手册，需求、设计、测试等文档也可能复用。
- 集中实现可以统一缓存、错误处理和来源追溯，避免多个 Skill 各自读取 HTML 源码。
- 当前系统的资源访问已经走 MCP 运行时，原型能力继续以宿主内置工具形态新增会破坏运行时一致性。
- 通过 MCP 暴露后，Skill 是否使用由其 `skill.md` 指引和执行时意图决定，而不是由 Skill 自己重复实现解析逻辑。

**备选方案**：
- 仅在 `write-user-manual` 下实现私有脚本。
  缺点是能力难复用，且多个 Skill 会逐渐出现重复实现和不一致解析结果。

### 决策2：采用“原始原型包 + 派生索引/页面事实”双层存储

**选择**：
- 原始 Axure 包继续放在 `project-facts/prototypes/` 下，由用户维护。
- 系统自动生成派生产物，放在 `project-facts/generated/prototypes/` 下。

派生产物分两层：
- `prototype-packages.json`：记录包根目录、入口页、扫描时间、文件指纹。
- `page-index.json`：记录页面清单、页面标题、相对路径、候选页面名、入出链关系。
- `pages/<page-id>.json`：记录结构化页面事实。

**理由**：
- 原始包和派生结果职责清晰，符合“人工事实只读、派生结果可重建”的原则。
- 解析成本可摊销到缓存，写作时无需每次重扫整个导出目录。
- 后续如果增加 UI 浏览能力或全文检索，可以直接复用派生产物。

**备选方案**：
- 每次 Skill 调用时即时扫描整个 Axure 包。
  缺点是耗时高、重复工作多，而且无法稳定复用解析结果。

### 决策3：模块到页面关系以模块档案声明为准，解析器只负责页面匹配和补充事实

**选择**：模块档案里的页面名称列表仍然是“模块关联哪些页面”的权威依据。解析器根据页面名称、文件名和标题在 `page-index.json` 中匹配实际页面，并将匹配结果提供给 Agent/Skill。

**理由**：
- 这符合当前事实维护模式，避免让 Agent 自行猜测模块和页面关系。
- 人工页面名通常更接近业务语义，适合作为写作目标入口。
- 即使 Axure 包目录结构变化，只要页面名称仍可匹配，写作链路仍可保持稳定。

**备选方案**：
- 完全由系统根据页面路径或跳转关系推断模块归属。
  缺点是误配风险高，且会削弱模块档案作为权威事实源的定位。

### 决策4：页面解析采用“HTML DOM 提取 + Axure 特征补充”的两阶段策略

**选择**：
- 第一阶段：解析页面 HTML，提取标题、可见文本、按钮、输入框、表格、选项卡、对话框、链接等通用元素。
- 第二阶段：针对 Axure 导出特征文件和结构命名补充页面关系与交互信息，例如页面跳转目标、热点区域、动态面板、弹层触发等。

页面事实输出统一为规范结构，例如：
- `page_id`
- `page_name`
- `source_path`
- `title`
- `layout_sections`
- `elements.buttons`
- `elements.inputs`
- `elements.tables`
- `elements.tabs`
- `elements.dialogs`
- `messages`
- `interactions`
- `outgoing_links`
- `evidence`
- `parser_warnings`

推荐再补一个适合 LLM 使用的聚合字段：
- `llm_summary`

其中 `llm_summary` 不是模型生成内容，而是解析器基于结构化事实拼装出的紧凑文本摘要，例如：
- 页面定位：页面名、标题、来源路径
- 关键区域：顶部筛选区、列表区、详情弹窗
- 关键控件：按钮、输入框、表格列
- 用户可见反馈：提示语、空态、错误提示
- 主要交互：查询、新增、编辑、删除、页面跳转

**理由**：
- 单靠 DOM 只能拿到静态文本，无法较好描述 Axure 特有交互。
- 单靠 Axure 特征解析又难以兼容普通 HTML 页面或前端静态页面。
- 两阶段策略既保留通用性，也能为 Axure 页面提供更高质量的结构化结果。

**备选方案**：
- 只读取 HTML 文本。
  缺点是无法提取交互和页面结构，价值不足。
- 引入浏览器渲染和视觉识别。
  缺点是依赖更重、实现复杂度高，不适合当前阶段。

### 决策4.1：解析器输出“结构化 JSON + LLM 友好摘要”，而不是只输出一种格式

**选择**：
- 页面事实文件保存完整结构化 JSON，供程序与 MCP 工具使用。
- MCP 返回中同时提供结构化字段和 `llm_summary`，供 agent/skill 直接注入上下文。

**理由**：
- 纯 JSON 适合程序处理，但直接喂给 LLM 可读性一般。
- 纯文本摘要便于模型理解，但不利于工具链复用和后续扩展。
- 双表示可以同时满足“可调用”和“可写作”两类需求。

### 决策5：系统自动在“派生视图刷新”与“MCP 查询前”确保原型索引新鲜

**选择**：
- 扩展现有模块档案派生流程，在生成模块索引时同时刷新原型派生索引。
- `prototypes.*` MCP 工具在执行前检查包目录指纹；若检测到原型包变更，则先增量重建相关派生产物，再返回结果。

**理由**：
- 不要求用户显式执行“重新解析原型”。
- 可以兼顾一致性和性能，避免每次启动都强制全量解析。
- 和现有 `ensure_generated_views` 风格一致，便于落地。

**备选方案**：
- 仅在服务启动时解析一次。
  缺点是对运行中更新原型包不敏感。
- 每次工具调用都全量重建。
  缺点是性能浪费明显。

### 决策6：通过 `prototypes.*` MCP namespace 提供“页面列表 + 页面详情”两类能力，轻重分离

**选择**：在 MCP server 中新增 `prototypes.*` namespace，至少暴露两类公共工具：

- `prototypes.list_pages(module_ref)`：
  返回该模块档案关联页面的匹配结果与摘要，包括页面名、路径、标题和匹配状态。
- `prototypes.get_page(page_ref)`：
  返回指定页面的结构化页面事实，包括元素、交互、可见消息和来源证据。

同时保留模块事实中的“页面 / 原型”摘要作为轻量事实入口，但页面详情能力统一通过 MCP 原型工具获取。

建议第一阶段的工具面定义为：

- `prototypes.list_pages(module_ref)`
  - 用途：列出某模块关联页面
  - 返回：页面名、页面标题、相对路径、匹配状态、候选页面引用

- `prototypes.get_page(page_ref)`
  - 用途：获取单页结构化页面事实
  - 返回：页面事实 JSON、`llm_summary`、来源路径、解析告警

可预留但不强制首期实现：

- `prototypes.list_packages()`
- `prototypes.get_sitemap(package_ref)`
- `prototypes.refresh(package_ref)`

**理由**：
- 这与当前 MCP 运行时的 namespace 治理方式一致，避免在宿主和 MCP 两套工具面之间分叉。
- 写作 Skill 可以先定位页面，再按需拉取细节，避免一次把所有页面事实塞进上下文。
- 页面详情响应中保留 `evidence` 和 `parser_warnings`，有利于写作时显式处理不确定项。

**备选方案**：
- 只提供一个“大而全”的原型上下文工具。
  缺点是输出过大，难以控制 token 和检索精度。

### 决策7：所有文档编写 Skill 都可获得 MCP 原型工具包装，但只有需要真实界面信息时才调用

**选择**：系统在主 Agent 与 Skill 执行层统一注册 `prototypes.*` 的 MCP wrapper 给文档编写类 Skill；Skill 是否调用由其 `skill.md` 正文约束和执行时上下文决定。

**理由**：
- 工具能力可共享，减少按 Skill 逐个注册的运维成本。
- 不是所有文档都需要页面细节；是否调用应由写作目标驱动，而不是强制加载。
- 与当前 “Skill 正文引导上下文利用” 的设计一致。

**备选方案**：
- 只有 `write-user-manual` 才注入原型工具。
  缺点是后续需求、设计、测试类 Skill 仍需重复接入。

## Risks / Trade-offs

- **[Axure 导出结构存在版本差异]** → 解析器采用通用 DOM 提取为底线，再对已识别出的 Axure 特征文件做增强；无法识别时返回 `parser_warnings`，不阻断整体流程。
- **[页面名称匹配可能不唯一]** → `prototypes.list_pages` 返回匹配状态和候选路径；当匹配不唯一时，Skill 必须优先使用模块档案声明页面名并在写作中保留待确认标记。
- **[页面事实过大导致上下文膨胀]** → 使用“页面列表 + 单页详情”两级工具，并限制详情只返回结构化摘要和关键证据，不直接返回原始 HTML。
- **[派生产物过期]** → 通过目录指纹和文件修改时间做增量刷新；查询前自动校验，避免用户手动维护缓存。
- **[解析结果被误认为权威事实]** → 在设计和输出字段上明确将模块档案作为权威来源，页面事实只作为派生结果与写作证据。
- **[MCP 公共工具契约不稳定]** → 原型工具采用宿主无关的 `module_ref` / `page_ref` 参数和结构化返回，避免暴露 ADK session 或宿主内部对象名。

## Migration Plan

1. 在 `project-facts/generated/` 下新增原型派生目录和 JSON 产物，不迁移或重写现有原始 Axure 包。
2. 扩展现有派生视图生成流程，使其在保留 `page-index.json` 兼容能力的同时产出更丰富的页面事实文件。
3. 在 `backend/mcp_runtime/` 中新增 `prototypes.*` namespace，并通过 `mcp_tools.py` 为主 Agent 和 Skill 提供对应 wrapper。
4. 保留旧的 `prototypes/` 原始目录结构和模块档案页面名称维护方式，不要求用户补录新字段。

## Delivery Shape

实现阶段应至少落地以下模块：

- `prototype parser`
  - 扫描原型包
  - 解析页面
  - 生成派生产物

- `prototype runtime access`
  - 读取派生产物
  - 暴露 `prototypes.*` MCP 工具
  - 适配 ADK MCP wrapper

## Module Design

建议按以下模块拆分实现，避免把扫描、解析、索引和 MCP 暴露耦合在一个文件里：

### 1. 原型包扫描器

职责：
- 发现 `project-facts/prototypes/` 下的原型包根目录
- 识别入口页、页面文件和资源目录
- 计算包级指纹，支持增量刷新

建议职责边界：
- 输入：`facts_root / prototypes`
- 输出：`PrototypePackageManifest`

建议结构：
- `backend/prototype_parser/package_scanner.py`
- `backend/prototype_parser/models.py`

### 2. 页面解析器

职责：
- 解析单个 HTML 页面
- 提取结构化页面元素
- 提取页面跳转和 Axure 特征交互
- 生成 `llm_summary`

建议子步骤：
- `html_reader`：读取并规范化 HTML
- `dom_extractor`：提取标题、文本、按钮、输入、表格、链接
- `axure_enricher`：提取跳转、热点、动态面板等 Axure 特征
- `summary_builder`：从结构化事实拼装 `llm_summary`

建议结构：
- `backend/prototype_parser/page_parser.py`
- `backend/prototype_parser/dom_extractor.py`
- `backend/prototype_parser/axure_enricher.py`
- `backend/prototype_parser/summary_builder.py`

### 3. 派生产物仓库

职责：
- 将解析结果写入 `project-facts/generated/prototypes/`
- 提供页面索引与单页事实读取接口
- 屏蔽 JSON 文件组织细节

建议结构：
- `backend/prototype_parser/repository.py`

### 4. MCP Namespace 适配层

职责：
- 将派生产物仓库包装成 MCP 工具
- 做参数校验、错误转换、返回结构组装

建议结构：
- `backend/mcp_runtime/prototypes_namespace.py`

### 5. ADK MCP 工具包装层

职责：
- 将 `prototypes.*` MCP 工具包装成 ADK 可调用函数
- 将 `llm_summary` 与必要事实写入当前轮次上下文

建议结构：
- 在 `backend/agent/adk/mcp_tools.py` 中新增 `prototypes.*` wrappers

## Data Shapes

建议至少定义以下内部数据结构：

### PrototypePackageManifest

```json
{
  "package_id": "axure-export",
  "package_name": "axure-export",
  "root_path": "prototypes/axure-export",
  "entry_page": "index.html",
  "fingerprint": "sha256:...",
  "page_count": 18,
  "updated_at": "2026-04-02T10:00:00Z"
}
```

### PrototypePageIndexItem

```json
{
  "page_id": "page-user-list",
  "page_name": "用户列表页",
  "title": "用户管理",
  "package_id": "axure-export",
  "source_path": "prototypes/axure-export/用户列表页.html",
  "relative_path": "axure-export/用户列表页.html",
  "outgoing_page_ids": ["page-user-detail"],
  "aliases": ["用户列表", "用户管理列表页"]
}
```

### PrototypePageFact

```json
{
  "page_id": "page-user-list",
  "page_name": "用户列表页",
  "title": "用户管理",
  "source_path": "prototypes/axure-export/用户列表页.html",
  "layout_sections": [
    "顶部查询区",
    "列表区",
    "分页区"
  ],
  "elements": {
    "buttons": ["查询", "重置", "新增用户", "导出"],
    "inputs": ["用户名", "手机号"],
    "tables": [
      {
        "name": "用户列表",
        "columns": ["用户名", "姓名", "状态", "角色", "创建时间"]
      }
    ],
    "dialogs": ["新增用户"],
    "tabs": [],
    "links": ["详情"]
  },
  "messages": ["新增成功", "未查询到数据"],
  "interactions": [
    "点击【查询】刷新用户列表",
    "点击【新增用户】打开“新增用户”对话框",
    "点击列表中的【详情】跳转到用户详情页"
  ],
  "outgoing_links": [
    {
      "label": "详情",
      "target_page_id": "page-user-detail"
    }
  ],
  "evidence": [
    "按钮: 查询",
    "表格列: 用户名 / 姓名 / 状态"
  ],
  "parser_warnings": [],
  "llm_summary": "页面“用户列表页”..."
}
```

## MCP Contracts

建议第一阶段把 MCP 返回 schema 固定下来，避免后续 agent/skill 适配抖动。

### `prototypes.list_pages(module_ref)`

输入：

```json
{
  "module_ref": "用户管理"
}
```

输出：

```json
{
  "module": {
    "id": "mod-123",
    "name": "用户管理"
  },
  "pages": [
    {
      "page_name": "用户列表页",
      "page_ref": "page-user-list",
      "title": "用户管理",
      "relative_path": "axure-export/用户列表页.html",
      "match_status": "matched"
    }
  ],
  "llm_summary": "模块“用户管理”关联 2 个页面：用户列表页、用户详情页。"
}
```

### `prototypes.get_page(page_ref)`

输入：

```json
{
  "page_ref": "page-user-list"
}
```

输出：

```json
{
  "page": {
    "page_id": "page-user-list",
    "page_name": "用户列表页",
    "title": "用户管理",
    "relative_path": "axure-export/用户列表页.html"
  },
  "fact": {},
  "llm_summary": "页面“用户列表页”包含顶部查询区和用户列表区...",
  "parser_warnings": []
}
```

## Call Flow

建议运行流程如下：

1. 用户在模块档案中维护页面名称
2. 原型包解析器扫描 Axure 导出目录，生成索引和单页事实
3. `prototypes.list_pages(module_ref)` 根据模块档案页面名称匹配页面索引
4. Skill 根据页面清单决定要读取哪些页面
5. Skill 调用 `prototypes.get_page(page_ref)` 获取单页事实和 `llm_summary`
6. `mcp_tools.py` 将 `llm_summary` 和必要事实片段写入当前轮次上下文
7. 写作 Skill 基于这些事实编写文档

## Error Handling

建议明确以下错误类型，便于 MCP 和 Agent 统一处理：

- `prototype_package_missing`
- `prototype_page_not_found`
- `prototype_page_ambiguous`
- `prototype_parse_failed`
- `prototype_index_stale`

其中：
- `prototype_page_ambiguous` 应返回候选页面列表
- `prototype_parse_failed` 应返回页面路径和简要原因
- `prototype_index_stale` 应优先内部自动刷新，刷新失败后再返回错误

## Open Questions

- Axure 交互信息的提取精度第一阶段是否只覆盖页面跳转、弹层和点击动作，还是一并覆盖条件逻辑与变量联动？
- 是否需要在后续迭代中补充页面截图或 DOM 证据片段，帮助用户手册引用“如图所示”的场景？
- 除 Axure 包外，是否要在同一能力下兼容普通前端页面构建产物目录？本次设计预留通用 DOM 提取结构，但不作为交付范围。
