#!/usr/bin/env bash
set -euo pipefail

python -c "import bascula.ui.app as _app; print('UI_OK')"
python -c "import bascula.services.scale as _scale; print(hasattr(_scale, 'ScaleService'))"

PORT="${PORT:-8080}"
export PORT

python - <<'PY' &
import os
import threading
import time

import uvicorn

from bascula.web.app import app

config = uvicorn.Config(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8080")), log_level="warning")
server = uvicorn.Server(config)

thread = threading.Thread(target=server.run, daemon=True)
thread.start()
while not server.started:
    time.sleep(0.1)

with open("/tmp/ci-ui-smoke.pid", "w", encoding="utf-8") as handle:
    handle.write(str(os.getpid()))

thread.join()
PY
SERVER_PID_FILE="/tmp/ci-ui-smoke.pid"
for _ in $(seq 1 20); do
  if [[ -f "$SERVER_PID_FILE" ]]; then
    break
  fi
  sleep 0.1
done

curl -sf "http://127.0.0.1:${PORT}/" > /dev/null

if [[ -f "$SERVER_PID_FILE" ]]; then
  PY_PID=$(cat "$SERVER_PID_FILE")
  kill "$PY_PID" || true
  rm -f "$SERVER_PID_FILE"
fi
