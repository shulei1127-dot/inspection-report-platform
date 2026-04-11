#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_PORT="${APP_PORT:-8012}"
CARBONE_PORT="${CARBONE_PORT:-4010}"
CARBONE_CONTAINER_NAME="${CARBONE_CONTAINER_NAME:-inspection-carbone-verify}"
APP_HOST="${APP_HOST:-127.0.0.1}"
IMAGE_REF="${IMAGE_REF:-carbone/carbone-ee:latest}"

if [[ ! -x "${ROOT_DIR}/.venv/bin/uvicorn" ]]; then
  echo "Missing ${ROOT_DIR}/.venv/bin/uvicorn. Create the virtualenv and install requirements first." >&2
  exit 1
fi

if ! docker image inspect "${IMAGE_REF}" >/dev/null 2>&1; then
  cat >&2 <<EOF
Docker image ${IMAGE_REF} is not available locally.
Try pulling it first:
  docker pull ${IMAGE_REF}
If Docker Hub is unreachable from this shell environment, resolve networking before running this verification.
EOF
  exit 1
fi

cleanup() {
  if [[ -n "${APP_SESSION_PID:-}" ]] && kill -0 "${APP_SESSION_PID}" >/dev/null 2>&1; then
    kill "${APP_SESSION_PID}" >/dev/null 2>&1 || true
    wait "${APP_SESSION_PID}" 2>/dev/null || true
  fi
  docker rm -f "${CARBONE_CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR:-}"
}
trap cleanup EXIT

docker rm -f "${CARBONE_CONTAINER_NAME}" >/dev/null 2>&1 || true
docker run -d --rm \
  --name "${CARBONE_CONTAINER_NAME}" \
  -p "${CARBONE_PORT}:4000" \
  "${IMAGE_REF}" >/dev/null

for _ in {1..20}; do
  if curl -fsS "http://127.0.0.1:${CARBONE_PORT}/status" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "http://127.0.0.1:${CARBONE_PORT}/status" >/dev/null 2>&1; then
  echo "Carbone runtime did not become healthy on port ${CARBONE_PORT}." >&2
  docker logs --tail 200 "${CARBONE_CONTAINER_NAME}" >&2 || true
  exit 1
fi

TMP_DIR="$(mktemp -d)"
printf 'sample log\n' > "${TMP_DIR}/host.log"
printf 'service active\n' > "${TMP_DIR}/service.txt"
python3 -m zipfile -c "${TMP_DIR}/sample.zip" "${TMP_DIR}/host.log" "${TMP_DIR}/service.txt" >/dev/null

(
  cd "${ROOT_DIR}"
  APP_HOST="${APP_HOST}" \
  APP_PORT="${APP_PORT}" \
  CARBONE_BASE_URL="http://127.0.0.1:${CARBONE_PORT}" \
  .venv/bin/uvicorn app.main:app --host "${APP_HOST}" --port "${APP_PORT}" >/tmp/inspection-report-platform-render-verify.log 2>&1
) &
APP_SESSION_PID="$!"

for _ in {1..20}; do
  if curl -fsS "http://${APP_HOST}:${APP_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "http://${APP_HOST}:${APP_PORT}/health" >/dev/null 2>&1; then
  echo "FastAPI app did not become healthy on port ${APP_PORT}." >&2
  cat /tmp/inspection-report-platform-render-verify.log >&2 || true
  exit 1
fi

UPLOAD_RESPONSE="$(
  curl -fsS -X POST "http://${APP_HOST}:${APP_PORT}/api/tasks" \
    -F "file=@${TMP_DIR}/sample.zip" \
    -F "parser_profile=default" \
    -F "report_lang=zh-CN"
)"

TASK_ID="$(
  python3 - <<'PY' "${UPLOAD_RESPONSE}"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["data"]["task_id"])
PY
)"

REPORT_PAYLOAD_PATH="$(
  python3 - <<'PY' "${UPLOAD_RESPONSE}"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["data"]["report_payload_path"])
PY
)"

if [[ ! -f "${ROOT_DIR}/${REPORT_PAYLOAD_PATH}" ]]; then
  echo "Expected report payload does not exist: ${ROOT_DIR}/${REPORT_PAYLOAD_PATH}" >&2
  exit 1
fi

RENDER_RESPONSE="$(
  curl -fsS -X POST "http://${APP_HOST}:${APP_PORT}/api/tasks/${TASK_ID}/render-report"
)"

REPORT_FILE_PATH="$(
  python3 - <<'PY' "${RENDER_RESPONSE}"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["data"]["report_file_path"])
PY
)"

ABS_REPORT_PATH="${ROOT_DIR}/${REPORT_FILE_PATH}"
if [[ ! -f "${ABS_REPORT_PATH}" ]]; then
  echo "Expected rendered report does not exist: ${ABS_REPORT_PATH}" >&2
  exit 1
fi

python3 - <<'PY' "${ABS_REPORT_PATH}"
import sys
from pathlib import Path
from zipfile import ZipFile

report_path = Path(sys.argv[1])
with ZipFile(report_path) as zf:
    assert zf.testzip() is None
    assert "word/document.xml" in zf.namelist()
print(report_path)
PY

echo "Carbone render verification succeeded."
echo "Task ID: ${TASK_ID}"
echo "Report payload: ${REPORT_PAYLOAD_PATH}"
echo "Rendered report: ${REPORT_FILE_PATH}"
