## Context

当前系统使用单一 LLM 配置（`is_default=True` 的模型）服务所有 Agent：document_orchestrator（意图理解/路由）和 doc_worker_*（文档写作执行）共用同一模型。

观察到的问题：主 Agent 用复杂 instruction 决策树弥补标准 LLM 推理能力不足，但随着对话场景增多，决策树膨胀且仍有漏洞（工具误用、意图误判）。Sub-agent 的写作执行任务边界清晰，对推理能力要求低，用标准模型即可。

现有配置体系：`LLMConfig` 有 `is_default` 字段，`get_default()` 返回唯一默认模型。配置存储在 `llm_configs.json`，UI 支持多模型管理。

## Goals / Non-Goals

**Goals:**
- 支持为 Orchestrator 和 Worker 分别指定 LLM 模型
- 现有单模型配置自动兼容（两个角色共用 default 模型，无需用户干预）
- 主 Agent instruction 随模型能力提升而精简，减少硬编码决策规则

**Non-Goals:**
- 不支持 Sub-agent 级别的细粒度模型配置（所有 worker 共用同一 worker 模型）
- 不引入新的模型提供商（范围不变）
- 不改变前端对话交互界面

## Decisions

### 决策 1：角色模型配置的存储方式

**选择：在 `LLMConfig` 中新增 `role` 字段（`orchestrator` / `worker` / `default`）**

- `default`：现有语义不变，两个角色均可使用
- `orchestrator`：指定为 Orchestrator 专用；若存在则主 Agent 优先使用
- `worker`：指定为 Worker 专用；若存在则 Sub-agent 优先使用

回退逻辑：若无 `orchestrator` 角色模型 → 回退到 `default`；`worker` 同理。

备选方案：新建独立配置字段（`orchestrator_model_id` / `worker_model_id`）存储引用 ID。
拒绝原因：需要额外的引用完整性管理，且不易在现有 UI 中展示。

### 决策 2：`get_litellm_model_config()` 接口扩展

新增 `role` 参数，默认值 `"default"`：

```python
def get_litellm_model_config(role: str = "default") -> Optional[LiteLLMModelConfig]
```

- `document_agent.py` 调用时传 `role="orchestrator"`
- `execute_skill_tool.py` 调用时传 `role="worker"`
- 其他调用方不传参数，行为不变

### 决策 3：主 Agent instruction 简化策略

配置思考型模型后，instruction 的调整方向：
- 移除具体的"禁止 X 操作"负向约束（模型自行判断）
- 保留高层次职责描述和工具用途说明
- 保留草稿状态 hint（has_draft / has_saved）——这是上下文注入，不是推理补丁

instruction 简化作为**可选优化**，在模型升级后按需调整，不作为本 change 的强制任务。

### 决策 4：LLMConfig.role 的默认值

现有所有已存储配置没有 `role` 字段 → 反序列化时默认为 `"default"`，向后兼容。

## Risks / Trade-offs

- **思考型模型延迟更高**（DeepSeek-R1 约 3–8s 首 token）→ 主 Agent 的路由决策会更慢，但 Sub-agent 写作过程不受影响；可在 UI 侧展示"正在理解意图…"状态
- **思考型模型费用更高** → 主 Agent 仅做意图路由（1–2 轮 LLM 调用），整体成本增量可控
- **用户未配置 orchestrator 专用模型** → 自动回退到 default，系统行为与现在完全一致，无感知

## Migration Plan

1. 数据迁移：现有 `llm_configs.json` 无需修改，反序列化时 `role` 默认为 `"default"`
2. 部署顺序：后端先部署（新增 role 字段向后兼容），前端 UI 随后更新
3. 回滚：删除 orchestrator 角色配置即回退到 default 模型
