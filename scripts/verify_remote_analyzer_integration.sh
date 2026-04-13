#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8013}"
ANALYZER_HOST="${ANALYZER_HOST:-127.0.0.1}"
ANALYZER_PORT="${ANALYZER_PORT:-8090}"
CARBONE_BASE_URL="${CARBONE_BASE_URL:-http://127.0.0.1:4000}"
VERIFY_RENDER="${VERIFY_RENDER:-auto}"

if [[ ! -x "${ROOT_DIR}/.venv/bin/uvicorn" ]]; then
  echo "Missing ${ROOT_DIR}/.venv/bin/uvicorn. Create the virtualenv and install requirements first." >&2
  exit 1
fi

step() {
  printf '\n==> %s\n' "$1"
}

pass() {
  printf 'PASS: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

cleanup() {
  if [[ -n "${APP_SESSION_PID:-}" ]] && kill -0 "${APP_SESSION_PID}" >/dev/null 2>&1; then
    kill "${APP_SESSION_PID}" >/dev/null 2>&1 || true
    wait "${APP_SESSION_PID}" 2>/dev/null || true
  fi
  if [[ -n "${ANALYZER_SESSION_PID:-}" ]] && kill -0 "${ANALYZER_SESSION_PID}" >/dev/null 2>&1; then
    kill "${ANALYZER_SESSION_PID}" >/dev/null 2>&1 || true
    wait "${ANALYZER_SESSION_PID}" 2>/dev/null || true
  fi
  rm -rf "${TMP_DIR:-}"
}
trap cleanup EXIT

wait_for_health() {
  local url="$1"
  local name="$2"

  for _ in {1..30}; do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      pass "${name} is healthy at ${url}"
      return 0
    fi
    sleep 1
  done

  return 1
}

verify_json_versions() {
  local unified_path="$1"
  local payload_path="$2"

  python3 - <<'PY' "${unified_path}" "${payload_path}"
import json
import sys
from pathlib import Path

unified_path = Path(sys.argv[1])
payload_path = Path(sys.argv[2])

unified = json.loads(unified_path.read_text())
payload = json.loads(payload_path.read_text())

assert unified["schema_version"] == "unified-json/v1", unified["schema_version"]
assert payload["payload_version"] == "report-payload/v1", payload["payload_version"]

print(unified["schema_version"])
print(payload["payload_version"])
PY
}

verify_docx() {
  local report_path="$1"

  python3 - <<'PY' "${report_path}"
import sys
from pathlib import Path
from zipfile import ZipFile

report_path = Path(sys.argv[1])
with ZipFile(report_path) as zf:
    assert zf.testzip() is None
    assert "word/document.xml" in zf.namelist()
print(report_path.stat().st_size)
PY
}

step "Preparing temporary input bundle"
TMP_DIR="$(mktemp -d)"
export TMP_DIR
python3 - <<'PY' "${ROOT_DIR}"
import sys
from pathlib import Path
from zipfile import ZipFile

root = Path(sys.argv[1])
tmp_dir = Path(__import__("os").environ["TMP_DIR"])
fixture_root = root / "tests" / "fixtures" / "input_bundle_spec_v1"
zip_path = tmp_dir / "input-bundle-spec-v1.zip"

with ZipFile(zip_path, "w") as zf:
    for file_path in sorted(fixture_root.rglob("*")):
        if file_path.is_file():
            zf.write(file_path, arcname=file_path.relative_to(fixture_root))

print(zip_path)
PY
SAMPLE_ZIP="${TMP_DIR}/input-bundle-spec-v1.zip"
[[ -f "${SAMPLE_ZIP}" ]] || fail "Fixture archive was not created."
pass "Created sample archive ${SAMPLE_ZIP}"

step "Starting log-analyzer-service"
(
  cd "${ROOT_DIR}/log-analyzer-service"
  ../.venv/bin/uvicorn app.main:app --host "${ANALYZER_HOST}" --port "${ANALYZER_PORT}" \
    >"${TMP_DIR}/log-analyzer-service.log" 2>&1
) &
ANALYZER_SESSION_PID="$!"

if ! wait_for_health "http://${ANALYZER_HOST}:${ANALYZER_PORT}/health" "log-analyzer-service"; then
  cat "${TMP_DIR}/log-analyzer-service.log" >&2 || true
  fail "log-analyzer-service did not become healthy."
fi

step "Starting platform in remote analyzer mode"
(
  cd "${ROOT_DIR}"
  ANALYZER_MODE="remote" \
  ANALYZER_BASE_URL="http://${ANALYZER_HOST}:${ANALYZER_PORT}" \
  ANALYZER_TIMEOUT_SECONDS="30" \
  REPORT_RENDERING_ENABLED="false" \
  .venv/bin/uvicorn app.main:app --host "${APP_HOST}" --port "${APP_PORT}" \
    >"${TMP_DIR}/inspection-platform.log" 2>&1
) &
APP_SESSION_PID="$!"

if ! wait_for_health "http://${APP_HOST}:${APP_PORT}/health" "inspection-report-platform"; then
  cat "${TMP_DIR}/inspection-platform.log" >&2 || true
  fail "inspection-report-platform did not become healthy."
fi

step "Uploading fixture archive through the platform"
UPLOAD_RESPONSE="$(
  curl -fsS -X POST "http://${APP_HOST}:${APP_PORT}/api/tasks" \
    -F "file=@${SAMPLE_ZIP}" \
    -F "parser_profile=default" \
    -F "report_lang=zh-CN"
)"
pass "Upload request returned successfully"

TASK_ID="$(
  python3 - <<'PY' "${UPLOAD_RESPONSE}"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["data"]["task_id"])
PY
)"
UNIFIED_JSON_PATH="$(
  python3 - <<'PY' "${UPLOAD_RESPONSE}"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["data"]["unified_json_path"])
PY
)"
REPORT_PAYLOAD_PATH="$(
  python3 - <<'PY' "${UPLOAD_RESPONSE}"
import json, sys
payload = json.loads(sys.argv[1])
print(payload["data"]["report_payload_path"])
PY
)"

[[ -n "${TASK_ID}" ]] || fail "Upload response did not contain task_id."
pass "Parsed task_id ${TASK_ID}"

ABS_UNIFIED_PATH="${ROOT_DIR}/${UNIFIED_JSON_PATH}"
ABS_REPORT_PAYLOAD_PATH="${ROOT_DIR}/${REPORT_PAYLOAD_PATH}"

step "Validating generated task artifacts"
[[ -f "${ABS_UNIFIED_PATH}" ]] || fail "Missing unified.json: ${ABS_UNIFIED_PATH}"
pass "Found unified.json at ${UNIFIED_JSON_PATH}"

[[ -f "${ABS_REPORT_PAYLOAD_PATH}" ]] || fail "Missing report_payload.json: ${ABS_REPORT_PAYLOAD_PATH}"
pass "Found report_payload.json at ${REPORT_PAYLOAD_PATH}"

VERSIONS_OUTPUT="$(verify_json_versions "${ABS_UNIFIED_PATH}" "${ABS_REPORT_PAYLOAD_PATH}")"
UNIFIED_VERSION="$(printf '%s\n' "${VERSIONS_OUTPUT}" | sed -n '1p')"
PAYLOAD_VERSION="$(printf '%s\n' "${VERSIONS_OUTPUT}" | sed -n '2p')"
pass "Verified unified.json schema_version=${UNIFIED_VERSION}"
pass "Verified report_payload.json payload_version=${PAYLOAD_VERSION}"

step "Checking optional render verification"
SHOULD_VERIFY_RENDER="0"
case "${VERIFY_RENDER}" in
  1|true|TRUE|yes|YES)
    SHOULD_VERIFY_RENDER="1"
    ;;
  auto|AUTO)
    if curl -fsS "${CARBONE_BASE_URL%/}/status" >/dev/null 2>&1; then
      SHOULD_VERIFY_RENDER="1"
    fi
    ;;
  0|false|FALSE|no|NO)
    SHOULD_VERIFY_RENDER="0"
    ;;
  *)
    fail "Unsupported VERIFY_RENDER value: ${VERIFY_RENDER}"
    ;;
esac

if [[ "${SHOULD_VERIFY_RENDER}" == "1" ]]; then
  if ! curl -fsS "${CARBONE_BASE_URL%/}/status" >/dev/null 2>&1; then
    fail "VERIFY_RENDER requested but Carbone is not reachable at ${CARBONE_BASE_URL}/status"
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
  [[ -f "${ABS_REPORT_PATH}" ]] || fail "Missing rendered report: ${ABS_REPORT_PATH}"
  DOCX_SIZE="$(verify_docx "${ABS_REPORT_PATH}")"
  pass "Verified rendered DOCX at ${REPORT_FILE_PATH} (${DOCX_SIZE} bytes)"
else
  printf 'SKIP: Render verification not requested or Carbone not available.\n'
fi

step "Remote analyzer integration verification completed"
echo "Task ID: ${TASK_ID}"
echo "unified.json: ${UNIFIED_JSON_PATH}"
echo "report_payload.json: ${REPORT_PAYLOAD_PATH}"
