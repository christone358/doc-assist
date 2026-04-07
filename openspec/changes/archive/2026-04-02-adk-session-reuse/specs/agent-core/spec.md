## MODIFIED Requirements

### Requirement: Agent 支持多轮对话交互
Agent 应该支持多轮对话模式，允许用户与 Agent 进行交互式的文档编写需求描述、反馈和修正。

#### Scenario: 对话上下文维护
- **WHEN** 用户启动文档编写任务后进行多次交互
- **THEN** Agent SHALL：
  1. 通过复用 ADK Session 维护经过压缩的事件历史（工具调用、LLM 推理、工具结果）
  2. 在后续轮次中，LLM 可直接访问历史事件摘要，无需重新加载已有信息
  3. ask_user 工具收集到的用户回答保留在 session 历史中，后续轮次可见
  4. 支持对话重新开始（conversation 删除后重建 session）

#### Scenario: 初始需求描述
- **WHEN** 用户首次提交文档编写需求
- **THEN** Agent 应该：
  - 理解需求并提出澄清问题（如需要）
  - 展示理解的需求概览
  - 邀请用户提供更多细节或反馈

#### Scenario: 反馈和修正
- **WHEN** 用户对生成的结果不满意或需要调整
- **THEN** Agent SHALL：
  - 从 session.state["draft_content"] 读取上一轮生成的草稿内容，无需用户重新描述
  - 理解用户的修正意图，基于草稿和历史上下文执行修改
  - 展示修改内容，再次邀请用户反馈

#### Scenario: 逐步完善
- **WHEN** 用户通过多轮对话逐步完善文档
- **THEN** Agent SHALL：
  - 在每一轮写作完成后将草稿写入 session.state["draft_content"]
  - 后续轮次 get_current_draft 工具从 session.state 直接读取最新草稿
  - 支持用户查看修改历史（通过 ConversationManager 中的 rounds 记录）

#### Scenario: 对话结束和输出
- **WHEN** 用户确认文档完成
- **THEN** Agent 应该：
  - 将最终的文档保存为新版本（通过 ConversationManager 持久化）
  - 记录对话过程中的所有修改
  - 提供完整的对话记录和版本历史
  - 清空对话状态或保存对话记录供后续查看
