# startup-scripts Specification

## Purpose
TBD - created by archiving change quick-start-script. Update Purpose after archive.
## Requirements
### Requirement: 环境前置检查
脚本 SHALL 在启动任何服务前检查运行环境，不满足条件时输出明确错误并退出（exit 1）。

#### Scenario: Python 版本不满足
- **WHEN** 系统 Python 版本低于 3.11
- **THEN** 脚本输出红色错误信息 "Python 3.11+ is required" 并退出

#### Scenario: Node.js 版本不满足
- **WHEN** 系统 Node.js 版本低于 18
- **THEN** 脚本输出红色错误信息 "Node.js 18+ is required" 并退出

#### Scenario: 端口已被占用
- **WHEN** 端口 8000 或 5173 已被其他进程占用
- **THEN** 脚本输出提示信息（含占用端口号）并退出

---

### Requirement: 自动安装依赖
脚本 SHALL 在后端或前端依赖过期时自动安装，避免不必要的重复安装。

#### Scenario: 首次启动（后端）
- **WHEN** `backend/.venv` 目录不存在
- **THEN** 脚本创建 venv 并执行 `pip install -r requirements.txt`

#### Scenario: requirements.txt 已变更
- **WHEN** `requirements.txt` 的修改时间晚于 `.venv/.last_install`
- **THEN** 脚本重新执行 `pip install -r requirements.txt` 并更新 `.last_install` 时间戳

#### Scenario: 依赖未变更
- **WHEN** `.venv` 存在且 `requirements.txt` 未变更
- **THEN** 跳过安装，直接启动

#### Scenario: 首次启动（前端）
- **WHEN** `frontend/node_modules` 目录不存在
- **THEN** 执行 `npm install`

#### Scenario: package.json 已变更
- **WHEN** `package.json` 的修改时间晚于 `node_modules/.last_install`
- **THEN** 重新执行 `npm install`

---

### Requirement: 并行启动前后端
脚本 SHALL 将前后端进程在后台并行启动，并将 PID 保存以供停止使用。

#### Scenario: 两个服务均成功启动
- **WHEN** 执行 `./start.sh`
- **THEN** 后端在后台启动并将 PID 写入 `.pids/backend.pid`，前端在后台启动并将 PID 写入 `.pids/frontend.pid`

#### Scenario: 单独启动后端
- **WHEN** 执行 `./start.sh backend`
- **THEN** 仅启动后端（前台运行，输出实时日志）

#### Scenario: 单独启动前端
- **WHEN** 执行 `./start.sh frontend`
- **THEN** 仅启动前端（前台运行，输出实时日志）

---

### Requirement: 启动就绪检测
脚本 SHALL 在服务就绪后再打印访问地址，最多等待 30 秒。

#### Scenario: 后端就绪
- **WHEN** `GET http://localhost:8000/health` 返回 200
- **THEN** 脚本打印 "✓ Backend ready: http://localhost:8000"

#### Scenario: 后端启动超时
- **WHEN** 30 秒内 `/health` 未返回 200
- **THEN** 脚本打印黄色警告 "Backend may not be ready, check logs/backend.log"

#### Scenario: 前端就绪
- **WHEN** 端口 5173 可连接
- **THEN** 脚本打印 "✓ Frontend ready: http://localhost:5173"

---

### Requirement: 日志分流
脚本 SHALL 将前后端日志分别写入文件，同时在终端实时显示。

#### Scenario: 日志写入文件
- **WHEN** 任一服务有输出
- **THEN** 输出追加写入对应日志文件（`logs/backend.log` / `logs/frontend.log`）

#### Scenario: 终端实时显示
- **WHEN** 日志产生
- **THEN** 终端显示带颜色前缀的实时输出（`[BACKEND]` 绿色，`[FRONTEND]` 蓝色）

---

### Requirement: 优雅停止
`stop.sh` SHALL 读取 PID 文件并终止对应进程，清理 PID 文件。

#### Scenario: 正常停止
- **WHEN** 执行 `./stop.sh`
- **THEN** 读取 `.pids/` 下的 PID 文件，发送 SIGTERM 终止进程，删除 PID 文件

#### Scenario: 进程已不存在
- **WHEN** PID 文件存在但对应进程不运行
- **THEN** 脚本提示 "Process not running" 并删除过期 PID 文件

#### Scenario: 无 PID 文件
- **WHEN** `.pids/` 目录不存在或为空
- **THEN** 脚本提示 "No services running" 并退出

