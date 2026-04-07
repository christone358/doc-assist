## 1. 环境检查

- [x] 1.1 实现 Python 版本检查（要求 3.11+，不满足时输出错误并 exit 1）
- [x] 1.2 实现 Node.js 版本检查（要求 18+，不满足时输出错误并 exit 1）
- [x] 1.3 实现端口占用检测（8000 和 5173，占用时输出提示并 exit 1）

## 2. 依赖安装逻辑

- [x] 2.1 实现后端依赖检查：venv 不存在时创建并安装
- [x] 2.2 实现 requirements.txt 变更检测（mtime 比较）并按需重新安装
- [x] 2.3 实现前端依赖检查：node_modules 不存在时执行 npm install
- [x] 2.4 实现 package.json 变更检测并按需重新安装

## 3. 服务启动

- [x] 3.1 实现后端后台启动（uvicorn），输出重定向到 logs/backend.log 并写入 .pids/backend.pid
- [x] 3.2 实现前端后台启动（npm run dev），输出重定向到 logs/frontend.log 并写入 .pids/frontend.pid
- [x] 3.3 实现 `./start.sh backend` 单独前台启动后端的逻辑
- [x] 3.4 实现 `./start.sh frontend` 单独前台启动前端的逻辑
- [x] 3.5 在启动前创建必要目录（logs/、.pids/、docs/、skills/、project-facts/）

## 4. 就绪检测与信息输出

- [x] 4.1 实现后端就绪检测：轮询 /health，最多等待 30 秒
- [x] 4.2 实现前端就绪检测：检测 5173 端口是否可连接，最多等待 30 秒
- [x] 4.3 就绪后打印带颜色的访问地址（前端 URL、后端 URL、API Docs URL）
- [x] 4.4 超时未就绪时打印黄色警告并指引查看日志文件

## 5. 日志实时显示

- [x] 5.1 实现 tail -f 实时跟随日志输出到终端，后端用绿色 [BACKEND] 前缀，前端用蓝色 [FRONTEND] 前缀
- [x] 5.2 Ctrl+C 时捕获 SIGINT，打印提示并优雅退出（不终止后台服务）

## 6. stop.sh 实现

- [x] 6.1 实现读取 .pids/backend.pid 并 SIGTERM 终止后端进程
- [x] 6.2 实现读取 .pids/frontend.pid 并 SIGTERM 终止前端进程
- [x] 6.3 处理进程已不存在的情况（提示并删除过期 PID 文件）
- [x] 6.4 处理 .pids/ 目录不存在的情况（提示 "No services running"）
- [x] 6.5 赋予 stop.sh 可执行权限（chmod +x）

## 7. 收尾

- [x] 7.1 在 .gitignore 追加 logs/ 和 .pids/
- [x] 7.2 手动测试：全新目录首次启动流程
- [x] 7.3 手动测试：stop.sh 停止服务流程
- [x] 7.4 手动测试：requirements.txt 变更后重启流程
