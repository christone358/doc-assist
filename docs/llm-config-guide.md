# LLM 配置和模型集成指南

## 概述

NextAgent Doc Assistant 支持 DeepSeek、通义千问（QWen）和 Ollama 本地模型。本指南说明如何配置和使用这些模型。

---

## 1. DeepSeek 配置

### 1.1 获取 API Key

1. 访问 [DeepSeek 平台](https://platform.deepseek.com)
2. 注册账号并登录
3. 进入「API Keys」页面，创建新的 API Key
4. 复制并妥善保存 API Key（仅显示一次）

### 1.2 支持的模型

| 模型名称 | 说明 | 适用场景 |
|---------|------|---------|
| `deepseek-chat` | DeepSeek-V3，通用对话 | 文档编写、需求理解 |
| `deepseek-reasoner` | DeepSeek-R1，深度推理 | 复杂分析、架构设计 |

### 1.3 配置参数

| 参数 | 说明 | 推荐值 |
|------|------|-------|
| `api_base` | API 地址 | `https://api.deepseek.com/v1` |
| `temperature` | 创意度（0-1） | `0.7`（文档编写） |
| `max_tokens` | 最大输出 tokens | `4096` |
| `top_p` | 采样概率 | `0.9` |

### 1.4 在 Web UI 中配置

1. 进入「⚙️ LLM 配置」标签
2. 点击「添加配置」
3. 填写：
   - 配置名称：自定义（如「DeepSeek V3」）
   - 服务商：DeepSeek
   - 模型：`deepseek-chat`
   - API 地址：`https://api.deepseek.com/v1`
   - API Token：粘贴你的 API Key
4. 点击「测试连接」验证
5. 点击「保存」，可选设为默认

---

## 2. 通义千问（QWen）配置

### 2.1 获取 API Key

1. 访问 [阿里云百炼平台](https://bailian.console.aliyun.com)
2. 开通 DashScope 服务
3. 在「API-KEY 管理」中创建 Key

### 2.2 支持的模型

| 模型名称 | 说明 | 适用场景 |
|---------|------|---------|
| `qwen-plus` | 千问 Plus，性价比高 | 常规文档编写 |
| `qwen-max` | 千问 Max，最强能力 | 高质量文档、复杂需求 |
| `qwen-turbo` | 千问 Turbo，速度快 | 快速草稿 |

### 2.3 配置参数

| 参数 | 说明 | 推荐值 |
|------|------|-------|
| `api_base` | API 地址 | `https://dashscope.aliyuncs.com/api/v1` |
| `temperature` | 创意度（0-1） | `0.7` |
| `max_tokens` | 最大输出 tokens | `4096` |

### 2.4 在 Web UI 中配置

步骤同 DeepSeek，服务商选择「QWen」即可。

---

## 3. 本地 OpenAI 兼容模型配置

适用于本地或局域网内部署的 OpenAI 兼容模型服务，例如：
- OMLX
- `qwen2.5-coder:14b-instruct-q5_K_S`
- `qwen3:8b`
- `llama3.1`
- `deepseek-r1`

### 3.1 推荐配置

| 参数 | 说明 | 示例值 |
|------|------|-------|
| `provider` | 服务商 | `ollama` |
| `model_name` | 本地服务暴露的真实模型名 | `qwen3:8b` / `Qwen3-9B` |
| `api_base` | 本地 OpenAI 兼容服务地址 | `http://127.0.0.1:11434` |
| `api_key` | OpenAI 兼容占位令牌 | 可留空 |

### 3.2 在 Web UI 中配置

1. 进入「⚙️ LLM 配置」标签
2. 点击「添加配置」
3. 选择「本地模型（OpenAI 兼容）」
4. 填写：
   - 配置名称：如「本地 Qwen3」
   - 模型：填写服务端真实模型名，例如 `qwen3:8b`
   - API 地址：`http://127.0.0.1:11434`
   - API Token：本地服务通常可留空
5. 点击「测试连接」验证

说明：
- 系统内部仍使用 `provider=ollama` 标识本地模型，以兼容现有代码和历史配置。
- 系统会自动把根地址补全为 OpenAI 兼容的 `/v1` 路径，无需手工填写。
- “测试连接”对本地模型会基于接口可达和返回结构判断，不再依赖模型必须精确回复某个固定文本。

---

## 4. 模型参数说明

### temperature（温度）

控制输出的随机性和创意度：
- `0.0 - 0.3`：保守、确定性强，适合格式化文档、技术规范
- `0.4 - 0.7`：平衡，适合大多数文档编写场景（**推荐**）
- `0.8 - 1.0`：创意性强，适合概念描述、创意内容

### max_tokens

控制单次响应的最大长度：
- `2048`：短文档、章节片段
- `4096`：中等长度文档（**推荐**）
- `8192`：长文档（需模型支持）

### top_p

与 temperature 配合使用，一般保持默认值 `0.9` 即可。

---

## 5. 模型切换

可在对话过程中通过「⚙️ LLM 配置」页面随时切换默认模型，切换后的新对话将使用新模型。

建议根据任务复杂度选择：
- 简单修改、格式调整 → `deepseek-chat` 或 `qwen-plus`（快速、经济）
- 完整文档编写、架构分析 → `deepseek-reasoner` 或 `qwen-max`（质量最佳）

---

## 6. 故障排查

| 错误 | 原因 | 解决方法 |
|------|------|---------|
| 连接测试失败 | API Key 错误 | 检查并重新输入 API Key |
| 响应超时 | 网络问题 | 检查网络，或稍后重试 |
| 模型不存在 | 模型名称错误 | 参考支持的模型列表 |
| 余额不足 | API 配额用完 | 充值后继续使用 |
| 本地模型连接失败 | 服务地址或模型名不匹配 | 确认服务商选择为“本地模型（OpenAI 兼容）”，地址填写 `http://<host>:<port>`，模型名填写服务实际暴露的名称 |
