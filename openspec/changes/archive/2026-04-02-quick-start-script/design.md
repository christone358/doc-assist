## Context

项目由 Python FastAPI 后端（端口 8000）和 SvelteKit 前端（端口 5173）组成。当前已有一个基础 `start.sh`，但功能较简单：没有完整的环境检查、没有进程 PID 管理、也没有优雅停止机制。需要在此基础上增强，使其成为真正可用的开发一键启动工具。

## Goals / Non-Goals

**Goals:**
- 执行 `./start.sh` 后，前后端均启动完毕，终端打印访问地址
- 自动检测 Python / Node.js 版本，不满足时给出清晰错误提示
- 自动安装/更新依赖（首次或 requirements.txt / package.json 变化时）
- 将前后端日志写入 `logs/` 目录，同时在终端输出带颜色的实时日志
- `./stop.sh` 读取 PID 文件，优雅终止所有相关进程
- 支持 `./start.sh backend` / `./start.sh frontend` 单独启动

**Non-Goals:**
- 不涉及生产部署（由 Docker Compose 负责）
- 不管理数据库迁移
- 不修改任何业务代码

## Decisions

**1. 用 Shell Script 还是 Makefile？**
选择 Shell Script（bash）。原因：macOS / Linux 开箱即用，无需额外工具；Makefile 对新成员不够直观。

**2. PID 管理方式**
将后端和前端进程 PID 写入 `.pids/backend.pid` 和 `.pids/frontend.pid`。`stop.sh` 读取并 `kill`，避免用 `pkill` 误杀同名进程。

**3. 依赖安装触发条件**
- 后端：`requirements.txt` 的 mtime 与 `.venv/.last_install` 的 mtime 比较
- 前端：`package.json` 的 mtime 与 `node_modules/.last_install` 比较
- 首次运行（venv / node_modules 不存在）无条件安装

**4. 日志文件**
前后端各自输出到 `logs/backend.log` 和 `logs/frontend.log`，同时通过 `tee` 实时输出到终端（带前缀颜色区分）。

**5. 启动就绪检测**
后端就绪：轮询 `http://localhost:8000/health`，最多等待 30 秒。
前端就绪：检测端口 5173 是否开放，最多等待 30 秒。
就绪后打印访问地址，用户体验更好。

## Risks / Trade-offs

- [Python venv 路径差异] macOS / Linux 下 `source .venv/bin/activate` 路径相同，Windows 不支持 → 本脚本明确只支持 macOS / Linux
- [端口占用] 若 8000 或 5173 已被占用，uvicorn / vite 会报错 → 启动前检测端口，提示用户手动释放
- [requirements.txt mtime 检测] 如果用户手动修改了包但未改 requirements.txt，不会重新安装 → 可用 `./start.sh --reinstall` 强制重装

## Migration Plan

1. 用新内容覆盖根目录 `start.sh`（已有文件）
2. 新增 `stop.sh`
3. 在 `.gitignore` 追加 `logs/` 和 `.pids/`
4. 无需数据迁移，不影响已有功能
