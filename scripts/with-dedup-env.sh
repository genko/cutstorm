#!/usr/bin/env bash
# Restart uvicorn inside cutstorm-app-1 with CUTSTORM_DEDUP=${1:-0}.
# Used by smoke-dedup parity test to flip the dedup flag without
# docker-compose recreation. After the smoke is done, `docker restart
# cutstorm-app-1` returns to the default (dedup=ON).
set -euo pipefail
VAL="${1:-0}"
echo "[with-dedup-env] setting CUTSTORM_DEDUP=$VAL"
docker exec cutstorm-app-1 sh -c 'for p in $(ps -ef | grep "uvicorn app.main" | grep -v grep | awk "{print \$2}"); do kill "$p" || true; done'
sleep 3
docker exec -d -e "CUTSTORM_DEDUP=$VAL" cutstorm-app-1 \
  sh -c 'uvicorn app.main:app --host 0.0.0.0 --port 8000 >/tmp/uvicorn.log 2>&1'
# Wait until /health responds.
for i in $(seq 1 30); do
  if curl -sS --max-time 1 http://localhost:8000/health | grep -q ok; then
    echo "[with-dedup-env] uvicorn up (CUTSTORM_DEDUP=$VAL)"
    exit 0
  fi
  sleep 1
done
echo "[with-dedup-env] timeout waiting for uvicorn"
exit 1
