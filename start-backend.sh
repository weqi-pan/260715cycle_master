#!/bin/bash
# Start Cycle Master backend
# Run: bash start-backend.sh

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Kill existing process on port 8000
PID=$(netstat -ano 2>/dev/null | grep ':8000.*LISTENING' | awk '{print $5}' | head -1)
if [ -n "$PID" ]; then
  taskkill //F //PID "$PID" 2>/dev/null
  echo "Killed old backend (PID $PID)"
  sleep 1
fi

cd "$ROOT/backend"
echo "Starting backend on http://localhost:8000"
./venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
