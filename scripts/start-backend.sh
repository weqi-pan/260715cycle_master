#!/bin/bash
# ============================================
# Cycle Master — 启动后端开发服务器
# 用法: bash scripts/start-backend.sh
# ============================================

# 脚本所在目录的父目录 = 项目根目录
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 终止已占用 8000 端口的进程
PID=$(netstat -ano 2>/dev/null | grep ':8000.*LISTENING' | awk '{print $5}' | head -1)
if [ -n "$PID" ]; then
  taskkill //F //PID "$PID" 2>/dev/null
  echo "[start-backend] 已终止旧进程 (PID $PID)"
  sleep 1
fi

cd "$ROOT/backend"
echo "[start-backend] 启动后端 → http://localhost:8000"
echo "[start-backend] API 文档 → http://localhost:8000/docs"

# 自动检测 Python 解释器（优先使用 venv，其次系统 Python）
if [ -f "./venv/Scripts/python.exe" ]; then
  PYTHON="./venv/Scripts/python.exe"
elif [ -f "./venv/bin/python" ]; then
  PYTHON="./venv/bin/python"
else
  PYTHON="python"
fi

$PYTHON -m uvicorn app.main:app --port 8000 --reload
