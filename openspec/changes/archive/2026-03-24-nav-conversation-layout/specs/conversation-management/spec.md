## MODIFIED Requirements

### Requirement: 对话记录的持久化和管理
系统应该能够保存每次用户编写为一个对话记录，并支持管理多个对话记录。

#### Scenario: 创建新对话
- **WHEN** 用户开始新的文档编写任务
- **THEN** 系统应该：
  1. 创建一个新的对话记录
  2. 记录对话的创建时间
  3. 为对话分配唯一的ID
  4. 使用时间戳格式初始命名（"对话 YYYY-MM-DD HH:MM"），待首轮完成后由自动命名能力替换

#### Scenario: 对话数据结构
- **WHEN** 系统保存对话时
- **THEN** 对话记录应包含：
  - `conversation_id`: 唯一标识符
  - `name`: 对话名称（初始为时间戳格式，可由自动命名更新）
  - `description`: 对话描述（可选）
  - `created_at`: 创建时间
  - `updated_at`: 最后更新时间
  - `status`: 对话状态（进行中/已完成）
  - `document_type`: 本次对话的主要文档类型（可选）
  - `conversation_rounds`: 对话轮次

#### Scenario: 对话列表按日期分组
- **WHEN** 用户查看对话列表时
- **THEN** 系统 SHALL：
  1. 按 `updated_at` 倒序排列所有对话
  2. 在前端按日期分为三组：今天、昨天、更早
  3. 每个分组显示分组标题和对应对话列表
  4. 对每个对话显示：名称（语义化或时间戳）

#### Scenario: 更新对话名称
- **WHEN** 系统或用户需要更新对话名称时
- **THEN** 系统 SHALL 提供 `PATCH /api/v1/conversations/{id}` 接口，接受 `{"name": "<new_name>"}` 请求体，更新成功返回更新后的对话对象
