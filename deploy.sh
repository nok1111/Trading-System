#!/bin/bash
# ============================================================
#  Alvora — Deploy Script for Linux Production Server
#  IP: 76.13.180.80
# ============================================================
#  Usage:
#    chmod +x deploy.sh
#    ./deploy.sh              # Full deploy (git pull + restart all)
#    ./deploy.sh pull         # Git pull only
#    ./deploy.sh restart      # Restart services only
#    ./deploy.sh status       # Check service status
#    ./deploy.sh logs         # Tail logs
#    ./deploy.sh stop         # Stop all services
# ============================================================

set -euo pipefail

# --- Config ---
PROJECT_DIR="/opt/trading-system"
VENV_DIR="${PROJECT_DIR}/venv"
PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"
GIT_BRANCH="main"

# Service ports
TRADING_CLIENT_PORT=8080
AI_SERVER_PORT=8001
AUTH_SERVER_PORT=8000

# Log directory
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"

# --- Helpers ---
log()   { echo -e "\033[32m[$(date '+%H:%M:%S')]\033[0m $*"; }
warn()  { echo -e "\033[33m[$(date '+%H:%M:%S')]\033[0m $*"; }
error() { echo -e "\033[31m[$(date '+%H:%M:%S')]\033[0m $*"; }

# --- Functions ---

git_pull() {
    log "Pulling latest code from ${GIT_BRANCH}..."
    cd "${PROJECT_DIR}"
    git fetch origin
    git reset --hard origin/${GIT_BRANCH}
    log "Git pull complete."
}

install_deps() {
    log "Installing Python dependencies..."
    ${PIP} install -r requirements.txt 2>/dev/null || ${PIP} install -e .
    log "Installing AI server dependencies..."
    cd "${PROJECT_DIR}/ai-server"
    ${PIP} install -e . 2>/dev/null || true
    cd "${PROJECT_DIR}/auth-server"
    ${PIP} install -e . 2>/dev/null || true
    cd "${PROJECT_DIR}"
    log "Dependencies installed."
}

build_frontend() {
    log "Building frontend..."
    cd "${PROJECT_DIR}/trading-client/desktop"
    npm install
    npm run build
    cd "${PROJECT_DIR}"
    log "Frontend built."
}

start_trading_client() {
    log "Starting Trading Client (port ${TRADING_CLIENT_PORT})..."
    pkill -f "run_server.py" 2>/dev/null || true
    sleep 1
    cd "${PROJECT_DIR}"
    nohup ${PYTHON} run_server.py --host 0.0.0.0 --port ${TRADING_CLIENT_PORT} \
        > "${LOG_DIR}/trading-client.log" 2>&1 &
    echo $! > "${LOG_DIR}/trading-client.pid"
    log "Trading Client started (PID: $(cat ${LOG_DIR}/trading-client.pid))"
}

start_ai_server() {
    log "Starting AI Server (port ${AI_SERVER_PORT})..."
    pkill -f "app.main:app.*${AI_SERVER_PORT}" 2>/dev/null || true
    sleep 1
    cd "${PROJECT_DIR}/ai-server"
    nohup ${PYTHON} -m uvicorn app.main:app --host 0.0.0.0 --port ${AI_SERVER_PORT} \
        > "${LOG_DIR}/ai-server.log" 2>&1 &
    echo $! > "${LOG_DIR}/ai-server.pid"
    log "AI Server started (PID: $(cat ${LOG_DIR}/ai-server.pid))"
}

start_auth_server() {
    log "Starting Auth Server (port ${AUTH_SERVER_PORT})..."
    pkill -f "app.main:app.*${AUTH_SERVER_PORT}" 2>/dev/null || true
    sleep 1
    cd "${PROJECT_DIR}/auth-server"
    nohup ${PYTHON} -m uvicorn app.main:app --host 0.0.0.0 --port ${AUTH_SERVER_PORT} \
        > "${LOG_DIR}/auth-server.log" 2>&1 &
    echo $! > "${LOG_DIR}/auth-server.pid"
    log "Auth Server started (PID: $(cat ${LOG_DIR}/auth-server.pid))"
}

start_all() {
    start_auth_server
    sleep 2
    start_ai_server
    sleep 2
    start_trading_client
    log "All services started."
    show_status
}

stop_all() {
    log "Stopping all services..."
    for svc in trading-client ai-server auth-server; do
        pidfile="${LOG_DIR}/${svc}.pid"
        if [ -f "${pidfile}" ]; then
            pid=$(cat "${pidfile}")
            kill "${pid}" 2>/dev/null || true
            rm -f "${pidfile}"
            log "  ${svc} (PID ${pid}) stopped."
        fi
    done
    pkill -f "run_server.py" 2>/dev/null || true
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    log "All services stopped."
}

show_status() {
    log "Service Status:"
    for svc in trading-client ai-server auth-server; do
        pidfile="${LOG_DIR}/${svc}.pid"
        port=$(case $svc in
            trading-client) echo ${TRADING_CLIENT_PORT} ;;
            ai-server)      echo ${AI_SERVER_PORT} ;;
            auth-server)    echo ${AUTH_SERVER_PORT} ;;
        esac)
        if [ -f "${pidfile}" ] && kill -0 $(cat "${pidfile}") 2>/dev/null; then
            log "  ✓ ${svc}  — running (PID $(cat ${pidfile}))  :${port}"
        else
            warn "  ✗ ${svc}  — stopped  :${port}"
        fi
    done
}

tail_logs() {
    log "Tailing all logs (Ctrl+C to exit)..."
    tail -f "${LOG_DIR}/trading-client.log" "${LOG_DIR}/ai-server.log" "${LOG_DIR}/auth-server.log"
}

# --- Main ---
case "${1:-full}" in
    pull)
        git_pull
        install_deps
        build_frontend
        ;;
    restart)
        stop_all
        start_all
        ;;
    stop)
        stop_all
        ;;
    status)
        show_status
        ;;
    logs)
        tail_logs
        ;;
    full|"")
        git_pull
        install_deps
        build_frontend
        stop_all
        start_all
        ;;
    *)
        echo "Usage: $0 {pull|restart|stop|status|logs|full}"
        exit 1
        ;;
esac
