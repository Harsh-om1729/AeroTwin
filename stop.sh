#!/bin/bash
# Stops AeroTwin (backend on :8000, Vite dev dashboard on :5173), wherever it was started.
#   ./stop.sh           stop it and say what happened
#   ./stop.sh --quiet   used by run.sh: say nothing if it was not running
# Only AeroTwin's own processes are touched, never another app on those ports.
BACKEND='uvicorn backend.main:app'
PORTS=(8000 5173)

aerotwin_pids() {
  pgrep -f "$BACKEND"
  for pid in $(lsof -ti tcp:5173 -sTCP:LISTEN 2>/dev/null); do
    ps -o command= -p "$pid" | grep -q vite && echo "$pid"
  done
}

pids=$(aerotwin_pids)
if [ -z "$pids" ]; then
  [ "$1" == "--quiet" ] || echo "AeroTwin is not running."
else
  kill $pids 2>/dev/null
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -z "$(aerotwin_pids)" ] && break
    sleep 0.5
  done
  left=$(aerotwin_pids)
  [ -n "$left" ] && kill -9 $left 2>/dev/null
  echo "AeroTwin stopped."
fi

for port in "${PORTS[@]}"; do
  other=$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null | head -1)
  if [ -n "$other" ] && ! ps -o command= -p "$other" | grep -q -e "$BACKEND" -e vite; then
    echo "Port $port is used by another app: $(ps -o comm= -p "$other") (pid $other). Close that app first."
    [ "$1" == "--quiet" ] && exit 1
  fi
done
exit 0
