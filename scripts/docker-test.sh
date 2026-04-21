#!/usr/bin/env bash
# Entry point for the docker-compose `test` profile: runs pytest in-process,
# then starts uvicorn and runs Playwright against it.
set -euo pipefail

cd /app
echo "==> pytest"
pytest -v tests/

echo "==> starting uvicorn"
UPLOADS_DIR=${UPLOADS_DIR:-/data/uploads} \
OUTPUTS_DIR=${OUTPUTS_DIR:-/data/outputs} \
MODELS_DIR=${MODELS_DIR:-/data/models} \
STATIC_DIR=${STATIC_DIR:-/app/static} \
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!
trap 'kill $UVICORN_PID 2>/dev/null || true' EXIT

echo "==> waiting for /health"
for i in $(seq 1 60); do
  if curl -fs http://127.0.0.1:8000/health >/dev/null; then
    echo "ready"
    break
  fi
  sleep 1
done

cd /fe
echo "==> playwright"
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8000 npm run test:e2e
