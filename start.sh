#!/usr/bin/env bash
# NextAgent Doc Assistant - 一键启动脚本
# 用法:
#   ./start.sh            # 启动前端 + 后端 + MCP（后台，实时日志输出到终端）
#   ./start.sh backend    # 仅前台启动后端
#   ./start.sh frontend   # 仅前台启动前端
#   ./start.sh mcp        # 仅前台启动 MCP server
#   ./start.sh --reinstall # 强制重新安装所有依赖

set -euo pipefail

# ─── 颜色 ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log_info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_success() { echo -e "${GREEN}${BOLD}$*${NC}"; }

# ─── 路径 ────────────────────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOGS_DIR="$PROJECT_ROOT/logs"
PIDS_DIR="$PROJECT_ROOT/.pids"

MODE="${1:-dev}"
REINSTALL=false
[[ "${1:-}" == "--reinstall" ]] && { REINSTALL=true; MODE="dev"; }

# ─── 1. 环境检查 ──────────────────────────────────────────────────────────────

check_python() {
    if ! command -v python3 &>/dev/null; then
        log_error "Python 3 未找到，请先安装 Python 3.11+"
        exit 1
    fi
    local ver
    ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    local major minor
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if (( major < 3 || (major == 3 && minor < 11) )); then
        log_error "Python 3.11+ is required (found $ver)"
        exit 1
    fi
    log_info "Python $ver ✓"
}

check_node() {
    if ! command -v node &>/dev/null; then
        log_error "Node.js 未找到，请先安装 Node.js 18+"
        exit 1
    fi
    local ver
    ver=$(node --version | sed 's/v//')
    local major
    major=$(echo "$ver" | cut -d. -f1)
    if (( major < 18 )); then
        log_error "Node.js 18+ is required (found v$ver)"
        exit 1
    fi
    log_info "Node.js v$ver ✓"
}

check_port() {
    local port="$1"
    local name="$2"
    if lsof -iTCP:"${port}" -sTCP:LISTEN -t &>/dev/null 2>&1; then
        log_error "Port ${port} (${name}) is already in use. Please free it first."
        log_error "  Check: lsof -iTCP:${port} -sTCP:LISTEN"
        exit 1
    fi
}

check_ports() {
    check_port 8000 "Backend"
    check_port 5173 "Frontend"
    check_port 8765 "MCP Server"
    log_info "端口 8000, 5173, 8765 可用 ✓"
}

# ─── 2. 依赖安装 ──────────────────────────────────────────────────────────────

install_backend_deps() {
    cd "$BACKEND_DIR"
    local venv="$BACKEND_DIR/.venv"
    local marker="$venv/.last_install"
    local req="$BACKEND_DIR/requirements.txt"

    # 创建 venv（首次）
    if [[ ! -d "$venv" ]]; then
        log_info "创建 Python 虚拟环境..."
        python3 -m venv "$venv"
    fi

    # 判断是否需要安装
    local need_install=false
    if $REINSTALL; then
        need_install=true
    elif [[ ! -f "$marker" ]]; then
        need_install=true
    elif [[ "$req" -nt "$marker" ]]; then
        log_info "requirements.txt 已变更，重新安装依赖..."
        need_install=true
    fi

    if $need_install; then
        log_info "安装后端依赖..."
        # shellcheck disable=SC1091
        source "$venv/bin/activate"
        pip install -q -r "$req"
        touch "$marker"
        log_info "后端依赖安装完成 ✓"
    else
        log_info "后端依赖已是最新 ✓"
    fi
}

install_frontend_deps() {
    cd "$FRONTEND_DIR"
    local marker="$FRONTEND_DIR/node_modules/.last_install"
    local pkg="$FRONTEND_DIR/package.json"

    local need_install=false
    if $REINSTALL; then
        need_install=true
    elif [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
        need_install=true
    elif [[ ! -f "$marker" ]]; then
        need_install=true
    elif [[ "$pkg" -nt "$marker" ]]; then
        log_info "package.json 已变更，重新安装依赖..."
        need_install=true
    fi

    if $need_install; then
        log_info "安装前端依赖..."
        npm install --silent
        touch "$marker"
        log_info "前端依赖安装完成 ✓"
    else
        log_info "前端依赖已是最新 ✓"
    fi
}

# ─── 3. 创建必要目录 ──────────────────────────────────────────────────────────

create_dirs() {
    mkdir -p "$LOGS_DIR" "$PIDS_DIR" \
             "$PROJECT_ROOT/docs" \
             "$PROJECT_ROOT/skills" \
             "$PROJECT_ROOT/project-facts/layer1-inventory" \
             "$PROJECT_ROOT/project-facts/layer2-core" \
             "$PROJECT_ROOT/project-facts/layer3-design"
}

# ─── 4. 就绪检测 ──────────────────────────────────────────────────────────────

wait_for_backend() {
    local max=30 i=0
    while (( i < max )); do
        if curl -sf "http://localhost:8000/health" &>/dev/null; then
            log_success "  ✓ Backend ready:  http://localhost:8000"
            log_success "  ✓ API Docs:       http://localhost:8000/docs"
            return 0
        fi
        sleep 1
        (( i++ ))
    done
    log_warn "Backend 未在 ${max}s 内就绪，请检查日志: $LOGS_DIR/backend.log"
    return 1
}

wait_for_frontend() {
    local max=30 i=0
    while (( i < max )); do
        if nc -z 127.0.0.1 5173 &>/dev/null 2>&1; then
            log_success "  ✓ Frontend ready: http://localhost:5173"
            return 0
        fi
        sleep 1
        (( i++ ))
    done
    log_warn "Frontend 未在 ${max}s 内就绪，请检查日志: $LOGS_DIR/frontend.log"
    return 1
}

wait_for_mcp() {
    local max=30 i=0
    while (( i < max )); do
        if nc -z 127.0.0.1 8765 &>/dev/null 2>&1; then
            log_success "  ✓ MCP ready:      http://localhost:8765/mcp"
            return 0
        fi
        sleep 1
        (( i++ ))
    done
    log_warn "MCP Server 未在 ${max}s 内就绪，请检查日志: $LOGS_DIR/mcp.log"
    return 1
}

# ─── 5. 启动函数 ──────────────────────────────────────────────────────────────

start_backend_bg() {
    cd "$BACKEND_DIR"
    # shellcheck disable=SC1091
    source "$BACKEND_DIR/.venv/bin/activate"
    log_info "后端启动中..."
    uvicorn main:app --host 0.0.0.0 --port 8000 \
        >> "$LOGS_DIR/backend.log" 2>&1 &
    echo $! > "$PIDS_DIR/backend.pid"
}

start_mcp_bg() {
    cd "$BACKEND_DIR"
    # shellcheck disable=SC1091
    source "$BACKEND_DIR/.venv/bin/activate"
    log_info "MCP Server 启动中..."
    python mcp_server.py --transport streamable-http \
        >> "$LOGS_DIR/mcp.log" 2>&1 &
    echo $! > "$PIDS_DIR/mcp.pid"
}

start_frontend_bg() {
    cd "$FRONTEND_DIR"
    log_info "前端启动中..."
    npm run dev \
        >> "$LOGS_DIR/frontend.log" 2>&1 &
    echo $! > "$PIDS_DIR/frontend.pid"
}

start_backend_fg() {
    cd "$BACKEND_DIR"
    # shellcheck disable=SC1091
    source "$BACKEND_DIR/.venv/bin/activate"
    log_info "前台启动后端（Ctrl+C 停止）..."
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
}

start_mcp_fg() {
    cd "$BACKEND_DIR"
    # shellcheck disable=SC1091
    source "$BACKEND_DIR/.venv/bin/activate"
    log_info "前台启动 MCP Server（Ctrl+C 停止）..."
    exec python mcp_server.py --transport streamable-http
}

start_frontend_fg() {
    cd "$FRONTEND_DIR"
    log_info "前台启动前端（Ctrl+C 停止）..."
    exec npm run dev
}

# ─── 5.2 日志跟随（带颜色前缀） ──────────────────────────────────────────────

follow_logs() {
    # Ctrl+C 退出日志跟随，但不停止后台服务
    trap 'echo -e "\n${YELLOW}[INFO]${NC} 已退出日志跟随（后台服务仍在运行）。运行 ./stop.sh 停止服务。"; exit 0' INT

    echo ""
    log_info "实时日志（Ctrl+C 退出跟随，服务继续运行）："
    echo "─────────────────────────────────────────────"

    tail -f "$LOGS_DIR/backend.log" \
        | sed "s/^/${GREEN}[BACKEND]${NC} /" &
    TAIL_BE=$!

    tail -f "$LOGS_DIR/frontend.log" \
        | sed "s/^/${BLUE}[FRONTEND]${NC} /" &
    TAIL_FE=$!

    tail -f "$LOGS_DIR/mcp.log" \
        | sed "s/^/${CYAN}[MCP]${NC} /" &
    TAIL_MCP=$!

    wait $TAIL_BE $TAIL_FE $TAIL_MCP
}

# ─── 主流程 ───────────────────────────────────────────────────────────────────

echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║   NextAgent Doc Assistant            ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

case "$MODE" in

    backend)
        check_python
        check_port 8000 "Backend"
        install_backend_deps
        create_dirs
        start_backend_fg
        ;;

    frontend)
        check_node
        check_port 5173 "Frontend"
        install_frontend_deps
        create_dirs
        start_frontend_fg
        ;;

    mcp)
        check_python
        check_port 8765 "MCP Server"
        install_backend_deps
        create_dirs
        start_mcp_fg
        ;;

    dev | --reinstall)
        check_python
        check_node
        check_ports

        install_backend_deps
        install_frontend_deps
        create_dirs

        # 清空旧日志
        : > "$LOGS_DIR/backend.log"
        : > "$LOGS_DIR/frontend.log"
        : > "$LOGS_DIR/mcp.log"

        start_backend_bg
        start_frontend_bg
        start_mcp_bg

        log_info "等待服务就绪..."
        wait_for_backend || true
        wait_for_frontend || true
        wait_for_mcp || true

        echo ""
        echo -e "${BOLD}服务已启动：${NC}"
        echo -e "  前端:   ${CYAN}http://localhost:5173${NC}"
        echo -e "  后端:   ${CYAN}http://localhost:8000${NC}"
        echo -e "  MCP:    ${CYAN}http://localhost:8765/mcp${NC}"
        echo -e "  API文档: ${CYAN}http://localhost:8000/docs${NC}"
        echo -e "  停止:   ${YELLOW}./stop.sh${NC}"
        echo ""

        follow_logs
        ;;

    *)
        log_error "未知模式: $MODE"
        echo "用法: $0 [dev|backend|frontend|mcp|--reinstall]"
        exit 1
        ;;
esac
