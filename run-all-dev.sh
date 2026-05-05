#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
WEB_DIR="${ROOT_DIR}/frontend/web"
DESKTOP_DIR="${ROOT_DIR}/frontend/desktop"

if [ -d "${BACKEND_DIR}/venv" ]; then
  VENV_ACTIVATE="${BACKEND_DIR}/venv/bin/activate"
elif [ -d "${BACKEND_DIR}/.venv" ]; then
  VENV_ACTIVATE="${BACKEND_DIR}/.venv/bin/activate"
elif [ -d "${ROOT_DIR}/.venv" ]; then
  VENV_ACTIVATE="${ROOT_DIR}/.venv/bin/activate"
else
  echo "No Python virtual environment found."
  echo "Expected one of:"
  echo "  ${BACKEND_DIR}/venv"
  echo "  ${BACKEND_DIR}/.venv"
  echo "  ${ROOT_DIR}/.venv"
  exit 1
fi

PIDS=()

start_service() {
  local label="$1"
  local workdir="$2"
  local command="$3"

  (
    cd "${workdir}"
    bash -lc "${command}"
  ) &

  local pid=$!
  PIDS+=("${pid}")
  echo "[start] ${label} (pid=${pid})"
}

cleanup() {
  echo
  echo "[stop] Shutting down all services..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
    fi
  done
}

trap cleanup INT TERM EXIT

start_service \
  "backend" \
  "${BACKEND_DIR}" \
  "source '${VENV_ACTIVATE}' && uvicorn app.main:app --reload --port 8000"

start_service \
  "web" \
  "${WEB_DIR}" \
  "npm run dev"

start_service \
  "desktop-1" \
  "${DESKTOP_DIR}" \
  "npm start"

start_service \
  "desktop-2" \
  "${DESKTOP_DIR}" \
  "npm start"

start_service \
  "desktop-3" \
  "${DESKTOP_DIR}" \
  "npm start"

echo
echo "All services started."
echo "Press Ctrl+C in this terminal to stop everything."
echo

wait
