## Why

目前项目启动需要手动进入 backend、frontend 两个目录分别安装依赖并执行启动命令，步骤繁琐，容易遗漏。需要一个一键脚本，让开发者和演示者无需了解项目内部结构即可快速把系统跑起来。

## What Changes

- 新增 `start.sh`：一键安装依赖并启动前端 + 后端（开发模式，带热重载）
- 增强环境检查：Python 版本、Node.js 版本、venv 是否存在
- 支持单独启动子服务：`./start.sh backend` / `./start.sh frontend`
- 后端启动前自动创建必要目录（docs、skills、project-facts）
- 启动后打印访问地址（前端 URL、后端 API URL、API 文档 URL）
- 新增 `stop.sh`：优雅停止所有后台进程

## Capabilities

### New Capabilities

- `startup-scripts`: 一键启动脚本，涵盖依赖安装、环境检查、进程管理、日志输出

### Modified Capabilities

（无）

## Impact

- 影响文件：根目录 `start.sh`、`stop.sh`
- 不修改任何已有业务代码
- 开发者体验改善，不影响生产部署流程（Docker Compose 独立维护）
