## 1. project-facts 存储结构迁移

- [x] 1.1 重写 `project-facts/README.md`，包含系统词汇表（6个词汇的含义、映射文件、检索方式）和各清单文件的格式规范与条目示例
- [x] 1.2 将现有 `layer1-inventory/modules.md` 迁移为新格式的 `project-facts/modules.md`，每个模块条目补充 `{#module-id}` 锚点和关联资源引用
- [x] 1.3 将现有 `layer1-inventory/usecases.md` 迁移为新格式的 `project-facts/usecases.md`，每条用例添加 `模块: {id}` 标签

## 2. 系统词汇表映射逻辑

- [x] 2.1 在 `backend/agent/` 中新建 `context_loader.py`，实现词汇到路径的映射函数：`load_context(vocab, module_id, facts_root) → List[str]`
- [x] 2.2 实现 `modules` 词汇的加载逻辑：全量读取 `modules.md`
- [x] 2.3 实现 `usecases / classes / interfaces` 词汇的加载逻辑：读取对应清单文件，按 `模块: {module_id}` 标签过滤条目
- [x] 2.4 实现 `prototypes` 词汇的加载逻辑：查找 `prototypes/{module_id}.*` 文件，找到则加载内容

## 3. 模块实体解析（Module Entity Resolution）

- [x] 3.1 在 `context_loader.py` 中实现 `resolve_module_id(user_message, modules_md_content, llm_service) → Optional[str]`
- [x] 3.2 实现精确字符串匹配：从 modules.md 解析所有模块名称和对应 ID，在用户消息中查找精确匹配
- [x] 3.3 实现 LLM 语义匹配兜底：构造 prompt 输入模块列表和用户消息，LLM 返回最匹配的模块 ID 或 null

## 4. Skill 上下文需求推断

- [x] 4.1 在 `backend/agent/core.py` 中新增 `_infer_context_needs(skill) → dict` 方法
- [x] 4.2 实现 LLM 推断调用：构造 prompt（Skill 全文 + 词汇表），解析 `CONTEXT: ...` 单行格式的返回结果（词汇列表，一次性全部加载）
- [x] 4.3 实现推断失败兜底：返回 `["modules", "usecases"]`
- [x] 4.4 推断结果（来源、词汇列表、Skill ID）写入日志

## 5. Agent Core 流程重构

- [x] 5.1 重构 `backend/agent/core.py` 的 `stream_message()` 方法，将现有 `_recommend_facts()` 调用替换为新的多步骤流程
- [x] 5.2 新增「上下文需求推断」步骤：调用 `_infer_context_needs(skill)`，yield status step "分析上下文需求..."
- [x] 5.3 新增「模块定位」步骤：调用 `resolve_module_id()`，yield status step "已定位模块: {名称}（{id}）"
- [x] 5.4 新增「加载必需上下文」步骤：按 required 词汇列表调用 `context_loader.load_context()`，yield status step "加载项目上下文：{摘要}"
- [x] 5.5 删除旧的 `_recommend_facts()` 方法

## 6. 更新现有 Skill 的 skill.md

- [x] 6.1 更新 `skills/write-requirements/skill.md`，在正文中用自然语言描述所需上下文（必需：用例信息、功能模块描述；可选：原型界面、接口清单）
- [x] 6.2 更新 `skills/write-design/skill.md`，描述所需上下文（必需：功能模块描述、类包清单；可选：接口清单、原型界面）
- [x] 6.3 更新 `skills/write-test-plan/skill.md`，描述所需上下文（必需：用例信息、功能模块描述；可选：接口清单）
