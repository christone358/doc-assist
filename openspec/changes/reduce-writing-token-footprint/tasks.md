## 1. Usage 观测模型

- [ ] 1.1 为写作链路定义整轮聚合 usage、分阶段 usage breakdown 和 usage_meta 数据结构
- [ ] 1.2 在 orchestrator、subagent、write_document、context_summary 各阶段接入 usage 采集与归类
- [ ] 1.3 调整 done chunk、`llm_info` 和历史持久化逻辑，使其输出聚合 usage 与 breakdown

## 2. 上下文传递收敛

- [ ] 2.1 梳理 `facts.*`、`prototypes.*`、`docs.*`、`skill.read_resource` 的历史返回内容与 working context 写入路径
- [ ] 2.2 将大体量工具结果改为“摘要进历史、原文进 working context”的双轨模式
- [ ] 2.3 修复历史正式版本正文与草稿基线的双重注入路径，统一为单一正文注入入口

## 3. 写作 prompt 预算优化

- [ ] 3.1 为 `write_document` 实现按来源分层的上下文预算构建、逻辑去重和优先级裁剪
- [ ] 3.2 收敛 Skill 参考资料注入策略，优先保留结构模板与关键规则，压缩低优先级长文本
- [ ] 3.3 收敛原型页注入策略，避免把大块页面 JSON 直接重复注入到最终 prompt
- [ ] 3.4 重写 `_generate_context_summary` 输入构造，改为优先消费结构化摘要和有限 excerpt

## 4. UI 与回归验证

- [ ] 4.1 调整前端 token meta bar，展示整轮总量并在有数据时展示阶段级 breakdown
- [ ] 4.2 更新历史对话恢复逻辑，兼容新的 `llm_info` 聚合 usage 与 breakdown 字段
- [ ] 4.3 为 usage 聚合、上下文预算、摘要化工具返回和展示恢复补充自动化测试
- [ ] 4.4 基于典型写作场景验证 token 降幅、写作品质和跨轮续写稳定性
