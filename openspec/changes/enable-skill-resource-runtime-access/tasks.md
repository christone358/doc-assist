## 1. 运行时资源上下文与安全边界

- [ ] 1.1 在 `backend/agent/adk/runner_adapter.py` 的 `ConversationContext` 中新增本轮 Skill 资源缓存字段，用于保存已读取参考资料与脚本输出
- [ ] 1.2 新增 Skill 资源路径解析与安全校验辅助逻辑，统一处理相对路径、根目录约束、隐藏文件与不支持类型校验
- [ ] 1.3 为 Skill 资源缓存增加按路径去重和 per-round 清理策略，避免跨轮污染与重复注入

## 2. Skill 本地资源工具实现

- [ ] 2.1 新增 `read_skill_resource(relative_path)` 工具，实现对当前 Skill 根目录内文本资源的读取、日志记录和上下文写入
- [ ] 2.2 新增 `run_skill_script(relative_path, payload)` 工具，实现对当前 Skill 根目录内 Python 脚本的受限执行、stdout 收集和上下文写入
- [ ] 2.3 为资源工具补充统一的错误处理与状态上报，覆盖缺失文件、越权路径、超时、非零退出码等分支

## 3. Skill 执行链路集成

- [ ] 3.1 在 `backend/agent/adk/execute_skill_tool.py` 中注册 Skill 本地资源工具，并更新固定执行规范，说明何时读取参考资料、何时执行脚本
- [ ] 3.2 保持现有 `_extract_and_load_skill_tools()` 机制兼容，使“动态导入工具模块”和“运行时访问本地资源”两条路径可以并存
- [ ] 3.3 在 `backend/agent/adk/write_document_tool.py` 中注入本轮已加载的 Skill 资源内容，并确保系统提示只保留最小不变约束

## 4. 验证与示例回归

- [ ] 4.1 为资源路径校验、文本读取、脚本执行成功/失败场景补充自动化测试
- [ ] 4.2 为 `write_document` 增加集成验证，确认已读取的 Skill 参考资料会进入最终写作上下文
- [ ] 4.3 选取至少一个现有 Skill（如 `user-manual-writter`）做端到端回归，验证 `references/*.md` 的运行时读取能够影响输出结果
