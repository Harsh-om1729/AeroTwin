#!/bin/bash
# AeroTwin one-command launcher.
#   ./run.sh         build (if needed) and serve everything on http://localhost:8000
#   ./run.sh --dev   backend on :8000 + Vite hot-reload dashboard on :5173
set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
PORT=8000

echo -e "${BLUE}✈  AeroTwin – Aero-Piston Engine Digital Twin${NC}"

# 1. Python dependencies
if ! python3 -c "import fastapi, uvicorn, sklearn, torch, yaml, pyarrow, joblib, scipy" 2>/dev/null; then
  echo -e "${YELLOW}Installing Python dependencies…${NC}"
  python3 -m pip install -r requirements.txt
fi

# 2. Trained models (train once if missing)
if [ ! -f models/metadata.json ]; then
  echo -e "${YELLOW}No trained models found – training (a few minutes)…${NC}"
  [ -f data/train_healthy.parquet ] || python3 -m aerotwin.simulator.generate_dataset
  python3 -m aerotwin.evaluation.train_models
fi

# 3. Dashboard dependencies
if [ ! -d dashboard/node_modules ]; then
  echo -e "${YELLOW}Installing dashboard dependencies…${NC}"
  (cd dashboard && npm install)
fi

if [ "$1" == "--dev" ]; then
  python3 -m uvicorn backend.main:app --reload --port $PORT &
  BACKEND_PID=$!
  (cd dashboard && npm run dev) &
  FRONTEND_PID=$!
  trap 'echo -e "\n${BLUE}Shutting down…${NC}"; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' SIGINT SIGTERM
  echo -e "${GREEN}✓ Dev mode:${NC} dashboard http://localhost:5173 · API http://localhost:$PORT/docs"
  wait
fi

# 4. Production build of the dashboard (only when sources changed)
if [ ! -f dashboard/dist/index.html ] || [ -n "$(find dashboard/src dashboard/index.html -newer dashboard/dist/index.html 2>/dev/null)" ]; then
  echo -e "${YELLOW}Building dashboard…${NC}"
  (cd dashboard && npm run build >/dev/null)
fi

# 5. Validation cache is built automatically on first start (~1 min, once)
[ -f cache/results.json ] || echo -e "${YELLOW}First start: evaluating models on 120 held-out flights (~1 min, cached afterwards)…${NC}"

echo -e "${GREEN}✓ Starting – open http://localhost:$PORT${NC}  (API docs: http://localhost:$PORT/docs, Ctrl+C to stop)"
( sleep 8; command -v open >/dev/null && open "http://localhost:$PORT" ) &
exec python3 -m uvicorn backend.main:app --port $PORT
