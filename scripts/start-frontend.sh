#!/bin/bash
# ============================================
# Cycle Master — 启动前端开发服务器
# 用法: bash scripts/start-frontend.sh
# ============================================

# 脚本所在目录的父目录 = 项目根目录
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 终止已占用 5173 端口的进程
PID=$(netstat -ano 2>/dev/null | grep ':5173.*LISTENING' | awk '{print $5}' | head -1)
if [ -n "$PID" ]; then
  taskkill //F //PID "$PID" 2>/dev/null
  echo "[start-frontend] 已终止旧进程 (PID $PID)"
  sleep 1
fi

cd "$ROOT/frontend"
echo "[start-frontend] 启动前端 → http://localhost:5173"

# 使用 npx 自动解析 vite
npx vite --port 5173
