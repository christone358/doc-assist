# 部署和运维文档

## 开发环境启动

### 前置条件

- Python 3.11+
- Node.js 20+
- 至少一个 LLM 服务（DeepSeek 或 QWen）的 API Key

### 一键启动

```bash
# 克隆/进入项目目录
cd doc-assit

# 启动前端 + 后端（开发模式，支持热重载）
./start.sh

# 或单独启动
./start.sh backend    # 仅后端 http://localhost:8000
./start.sh frontend   # 仅前端 http://localhost:5173
```

---

## 生产环境部署（Docker Compose）

### 1. 准备环境变量

```bash
cp .env.example .env
# 编辑 .env，配置 ALLOWED_ORIGINS 等
```

### 2. 构建并启动

```bash
docker compose up -d
```

访问 `http://your-server-ip`

### 3. 配置 LLM

启动后通过 Web UI 的「⚙️ LLM 配置」页面添加 DeepSeek 或 QWen 配置。

---

## 目录挂载说明

Docker Compose 将以下目录挂载到宿主机，数据持久化：

| 容器内路径 | 宿主机路径 | 说明 |
|-----------|-----------|------|
| `/data/docs` | `./docs` | 生成的文档 |
| `/data/project-facts` | `./project-facts` | 项目事实信息 |
| `/data/skills` | `./skills` | Skill 目录 |

---

## 安装 Skill

将 Skill 目录放入 `skills/` 文件夹，重启后端即可生效：

```bash
# 示例：安装第三方 Skill
cp -r my-skill/ doc-assit/skills/
./start.sh backend
```

---

## LLM 配置持久化

LLM 配置（含加密 API Key）保存在 `backend/llm_configs.json`。Docker 部署时此文件通过命名卷持久化。

**注意**：生产环境建议使用真正的加密（如系统 keyring 或 Vault），当前实现为 base64 混淆。

---

## 日志查看

```bash
# 开发模式
./start.sh     # 控制台直接查看

# Docker 模式
docker compose logs -f backend
docker compose logs -f frontend
```

---

## 备份

重要数据在以下目录，定期备份：

```bash
# 文档和对话记录
tar -czf backup-docs-$(date +%Y%m%d).tar.gz docs/

# 项目事实信息
tar -czf backup-facts-$(date +%Y%m%d).tar.gz project-facts/

# LLM 配置（含 API Key，妥善保管）
cp backend/llm_configs.json backup-llm-configs.json
```
