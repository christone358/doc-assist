# Agent API 文档

## 概述

NextAgent Doc Assistant 后端提供 REST API 和 WebSocket 接口，供前端调用。

基础地址：`http://localhost:8000`

---

## 1. 系统接口

### 1.1 健康检查

```
GET /health
```

**响应**

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "components": {
    "agent": "ready",
    "fact_info": "ready",
    "skills": "ready"
  }
}
```

---

## 2. 对话管理

### 2.1 创建对话

```
POST /api/v1/conversations
```

**请求体**

```json
{
  "name": "对话名称（可选）",
  "description": "对话描述（可选）",
  "document_type": "requirements"
}
```

**响应**

```json
{
  "conversation_id": "uuid",
  "name": "对话名称"
}
```

---

### 2.2 列出所有对话

```
GET /api/v1/conversations
```

**响应**

```json
{
  "conversations": [
    {
      "id": "uuid",
      "name": "对话名称",
      "status": "active",
      "document_type": "requirements",
      "created_at": "ISO8601",
      "updated_at": "ISO8601",
      "round_count": 3,
      "document_count": 1
    }
  ]
}
```

---

### 2.3 获取指定对话

```
GET /api/v1/conversations/{conversation_id}
```

**响应** 返回完整 ConversationInfo，包含所有轮次记录。

---

### 2.4 删除对话

```
DELETE /api/v1/conversations/{conversation_id}
```

**响应**

```json
{"message": "Conversation deleted"}
```

---

## 3. 聊天（非流式）

```
POST /api/v1/chat
```

**请求体**

```json
{
  "conversation_id": "uuid",
  "message": "用户输入的消息"
}
```

**响应**

```json
{
  "conversation_id": "uuid",
  "message": "Agent 的回复",
  "skill_invoked": "write-requirements",
  "documents_generated": [
    {
      "path": "requirements/xxx/2026-03-17/v1.0.0.md",
      "doc_type": "requirements",
      "doc_name": "xxx",
      "version": "1.0.0"
    }
  ]
}
```

---

## 4. WebSocket 流式聊天

```
ws://localhost:8000/ws/{conversation_id}
```

### 发送消息

```json
{"message": "用户输入"}
```

### 接收事件类型

| type | 说明 | 数据字段 |
|------|------|---------|
| `ack` | 消息已收到 | conversation_id |
| `status` | 处理状态 | content（状态描述） |
| `skill_start` | Skill 开始执行 | skill_id, content |
| `text` | LLM 输出片段 | content |
| `skill_end` | Skill 执行完成 | skill_id |
| `document` | 生成了文档 | path, doc_type, version |
| `done` | 响应完成 | — |
| `error` | 出错 | content（错误信息） |

---

## 5. Skill 接口

### 5.1 获取 Skill 列表

```
GET /api/v1/skills
```

**响应**

```json
{
  "skills": [
    {
      "id": "write-requirements",
      "name": "需求规格文档Skill",
      "description": "...",
      "skill_type": "requirements",
      "capabilities": ["需求分析", "用例描述"],
      "tags": ["需求", "规格"]
    }
  ]
}
```

---

### 5.2 获取单个 Skill

```
GET /api/v1/skills/{skill_id}
```

---

## 6. 项目事实信息

### 6.1 查询事实信息

```
GET /api/v1/fact-info?keyword=登录&system=业务保障管理系统
```

**查询参数**

| 参数 | 说明 |
|------|------|
| keyword | 关键词搜索 |
| system | 按所属系统过滤 |
| subsystem | 按所属子系统过滤 |
| status | 按状态过滤 |
| layer | 兼容历史 fact 数据的层级过滤，仅 legacy 数据使用 |
| category | 兼容历史 fact 数据的类别过滤，仅 legacy 数据使用 |

---

### 6.2 获取指定事实

```
GET /api/v1/fact-info/{fact_id}
```

**响应**

```json
{
  "id": "biz-asset-terminal-management",
  "name": "终端资产管理",
  "system": "业务保障管理系统",
  "subsystem": "保障资产管理",
  "description": "...",
  "usecases": []
}
```

---

## 7. 文档版本管理

### 7.1 列出所有文档

```
GET /api/v1/documents?doc_type=requirements
```

### 7.2 列出文档版本历史

```
GET /api/v1/documents/{doc_type}/{doc_name}/versions
```

### 7.3 获取最新版本

```
GET /api/v1/documents/{doc_type}/{doc_name}/latest
```

**响应**

```json
{
  "path": "requirements/xxx/2026-03-17/v1.0.0.md",
  "version": "1.0.0",
  "content": "# 文档内容..."
}
```

### 7.4 获取指定版本

```
GET /api/v1/documents/{doc_type}/{doc_name}/{date}/{version}
```

---

## 8. LLM 配置管理

### 8.1 获取配置列表

```
GET /api/v1/llm/configs
```

### 8.2 添加配置

```
POST /api/v1/llm/configs
```

**请求体**

```json
{
  "name": "DeepSeek 生产",
  "provider": "deepseek",
  "model_name": "deepseek-chat",
  "api_base": "https://api.deepseek.com/v1",
  "api_key": "sk-xxxxx",
  "temperature": 0.7,
  "max_tokens": 4096
}
```

### 8.3 更新配置

```
PATCH /api/v1/llm/configs/{config_id}
```

### 8.4 删除配置

```
DELETE /api/v1/llm/configs/{config_id}
```

### 8.5 设为默认

```
POST /api/v1/llm/configs/{config_id}/set-default
```

### 8.6 测试连接

```
POST /api/v1/llm/configs/{config_id}/test
```

**响应**

```json
{"success": true, "message": "连接成功"}
```
