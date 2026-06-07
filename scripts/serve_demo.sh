#!/usr/bin/env bash
# 전체 데모 스택을 한 번에 기동한다 (무료, 로컬).
#   1) Phoenix observability 서버 (localhost:6006)
#   2) mock 평가 데이터 적재
#   3) QualityAnalyst ADK Web UI (localhost:8000) — 심사자가 에이전트와 대화
#
# 사전: .venv-adk, .venv-phoenix 셋업 + .env 에 GOOGLE_API_KEY
# 사용: ./scripts/serve_demo.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ADK_PY="${ADK_PY:-.venv-adk/bin/python}"
PHX_PY="${PHX_PY:-.venv-phoenix/bin/python}"
PHX_URL="http://localhost:6006"

cleanup() {
  [[ -n "${PHX_PID:-}" ]] && kill "$PHX_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "▶ 1/3 Phoenix 서버 기동..."
PHOENIX_WORKING_DIR="$ROOT/.phoenix_data" "$PHX_PY" -m phoenix.server.main serve \
  > .phoenix_server.log 2>&1 &
PHX_PID=$!

for i in $(seq 1 20); do
  if curl -s -o /dev/null -w "%{http_code}" "$PHX_URL" 2>/dev/null | grep -q 200; then
    echo "  ✓ Phoenix UP ($PHX_URL)"; break
  fi
  sleep 2
done

echo "▶ 2/3 mock 평가 데이터 적재..."
"$PHX_PY" -m adk.phoenix_ingest --mock --project ai-novel-quality --endpoint "$PHX_URL" \
  2>/dev/null | grep "적재 완료" || echo "  (적재 로그 확인: .phoenix_server.log)"

echo "▶ 3/3 QualityAnalyst Web UI 기동 (localhost:8000)..."
echo "  브라우저에서 http://localhost:8000 → 'quality_analyst' 선택 → 대화"
echo "  (종료: Ctrl+C — Phoenix도 함께 종료됨)"
PHOENIX_BASE_URL="$PHX_URL" PYTHONPATH="$ROOT" "$ADK_PY" -m google.adk.cli web agents_dir --port 8000
