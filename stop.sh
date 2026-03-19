#!/usr/bin/env bash
# NextAgent Doc Assistant - Stop script

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDS_DIR="$PROJECT_ROOT/.pids"

if [[ ! -d "$PIDS_DIR" ]] || [[ -z "$(ls -A "$PIDS_DIR" 2>/dev/null)" ]]; then
    log_warn "No services running (no PID files found)"
    exit 0
fi

stop_service() {
    local name="$1"
    local pid_file="$PIDS_DIR/${name}.pid"

    if [[ ! -f "$pid_file" ]]; then
        log_warn "${name}: no PID file found, skipping"
        return
    fi

    local pid
    pid=$(cat "$pid_file")

    if ! kill -0 "$pid" &>/dev/null 2>&1; then
        log_warn "${name} (PID ${pid}): not running, removing stale PID file"
        rm -f "$pid_file"
        return
    fi

    log_info "Stopping ${name} (PID ${pid}) and its children..."

    # Kill the entire process group so child workers are also terminated
    local pgid
    pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ') || pgid=""

    if [[ -n "$pgid" && "$pgid" != "0" ]]; then
        kill -TERM "-${pgid}" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    else
        kill -TERM "$pid" 2>/dev/null || true
    fi

    # Wait up to 5 seconds
    local i=0
    while kill -0 "$pid" &>/dev/null 2>&1 && (( i < 5 )); do
        sleep 1; (( i++ ))
    done

    # Force kill if still running
    if kill -0 "$pid" &>/dev/null 2>&1; then
        log_warn "${name} did not respond to SIGTERM, sending SIGKILL..."
        [[ -n "$pgid" && "$pgid" != "0" ]] && \
            kill -KILL "-${pgid}" 2>/dev/null || \
            kill -KILL "$pid" 2>/dev/null || true
    fi

    # Also kill any process still holding the port
    local port=""
    [[ "$name" == "backend" ]]  && port="8000"
    [[ "$name" == "frontend" ]] && port="5173"
    if [[ -n "$port" ]]; then
        local stray
        stray=$(lsof -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null || true)
        if [[ -n "$stray" ]]; then
            log_warn "Port ${port} still occupied by PID ${stray}, killing..."
            kill -KILL $stray 2>/dev/null || true
        fi
    fi

    rm -f "$pid_file"
    log_info "${name} stopped ✓"
}

stop_service "backend"
stop_service "frontend"

rmdir "$PIDS_DIR" 2>/dev/null || true

echo ""
log_info "All services stopped."
