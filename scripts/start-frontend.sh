#!/bin/bash
# Start Cycle Master frontend
# Run: bash scripts/start-frontend.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Kill existing process on port 5173
PID=$(netstat -ano 2>/dev/null | grep ':5173.*LISTENING' | awk '{print $5}' | head -1)
if [ -n "$PID" ]; then
  taskkill //F //PID "$PID" 2>/dev/null
  echo "Killed old frontend (PID $PID)"
  sleep 1
fi

cd "$ROOT/frontend"
echo "Starting frontend on http://localhost:5173"
npx vite --port 5173
