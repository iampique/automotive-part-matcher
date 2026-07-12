#!/usr/bin/env bash
# Start backend + frontend for live demo. Run from repo root.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Starting demo servers ==="

# Backend
cd "$ROOT/backend"
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi
echo "Starting backend on :8000..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Frontend
cd "$ROOT/frontend"
echo "Starting frontend on :3000..."
npm run dev &
FRONTEND_PID=$!

sleep 5
echo ""
echo "Running preflight checks..."
cd "$ROOT/backend"
python scripts/preflight_demo.py || true

echo ""
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop both."
wait
