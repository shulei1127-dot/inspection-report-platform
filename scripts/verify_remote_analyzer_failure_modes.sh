#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_HOST="${APP_HOST:-127.0.0.1}"
ANALYZER_HOST="${ANALYZER_HOST:-127.0.0.1}"
ANALYZER_TIMEOUT_SECONDS="${ANALYZER_TIMEOUT_SECONDS:-3}"

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

stop_platform() {
  if [[ -n "${APP_SESSION_PID:-}" ]] && kill -0 "${APP_SESSION_PID}" >/dev/null 2>&1; then
    kill "${APP_SESSION_PID}" >/dev/null 2>&1 || true
    wait "${APP_SESSION_PID}" 2>/dev/null || true
  fi
  APP_SESSION_PID=""
}

stop_analyzer_mock() {
  if [[ -n "${ANALYZER_SESSION_PID:-}" ]] && kill -0 "${ANALYZER_SESSION_PID}" >/dev/null 2>&1; then
    kill "${ANALYZER_SESSION_PID}" >/dev/null 2>&1 || true
    wait "${ANALYZER_SESSION_PID}" 2>/dev/null || true
  fi
  ANALYZER_SESSION_PID=""
}

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

pick_free_port() {
  python3 - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

start_platform() {
  local analyzer_base_url="$1"
  local app_port="$2"

  stop_platform
  (
    cd "${ROOT_DIR}"
    ANALYZER_MODE="remote" \
    ANALYZER_BASE_URL="${analyzer_base_url}" \
    ANALYZER_TIMEOUT_SECONDS="${ANALYZER_TIMEOUT_SECONDS}" \
    REPORT_RENDERING_ENABLED="false" \
    .venv/bin/uvicorn app.main:app --host "${APP_HOST}" --port "${app_port}" \
      >"${TMP_DIR}/platform-${app_port}.log" 2>&1
  ) &
  APP_SESSION_PID="$!"

  if ! wait_for_health "http://${APP_HOST}:${app_port}/health" "inspection-report-platform"; then
    cat "${TMP_DIR}/platform-${app_port}.log" >&2 || true
    fail "inspection-report-platform did not become healthy on port ${app_port}."
  fi
}

start_analyzer_mock() {
  local scenario="$1"
  local analyzer_port="$2"

  stop_analyzer_mock
  (
    MOCK_SCENARIO="${scenario}" MOCK_PORT="${analyzer_port}" python3 - <<'PY'
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

scenario = os.environ["MOCK_SCENARIO"]
port = int(os.environ["MOCK_PORT"])


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self._send_json(
                200,
                {"status": "ok", "service": "mock-analyzer", "version": "0.0.0-test"},
            )
            return
        self.send_error(404)

    def do_POST(self):  # noqa: N802
        if self.path != "/analyze":
            self.send_error(404)
            return

        if scenario == "unsupported_source_type":
            self._send_json(
                400,
                {
                    "success": False,
                    "error": {
                        "code": "unsupported_source_type",
                        "message": "Only directory source is supported in analyze-request/v1.",
                        "details": {"source_type": "archive"},
                    },
                },
            )
            return

        if scenario == "source_not_found":
            self._send_json(
                404,
                {
                    "success": False,
                    "error": {
                        "code": "source_not_found",
                        "message": "Requested source directory does not exist.",
                        "details": {"path": "/tmp/missing"},
                    },
                },
            )
            return

        if scenario == "non_json_500":
            body = b"mock analyzer internal failure"
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(500)

    def log_message(self, format, *args):  # noqa: A003
        return


server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
server.serve_forever()
PY
  ) >"${TMP_DIR}/mock-analyzer-${scenario}.log" 2>&1 &
  ANALYZER_SESSION_PID="$!"

  if ! wait_for_health "http://${ANALYZER_HOST}:${analyzer_port}/health" "mock-analyzer(${scenario})"; then
    cat "${TMP_DIR}/mock-analyzer-${scenario}.log" >&2 || true
    fail "mock analyzer did not become healthy for scenario ${scenario}."
  fi
}

start_broken_analyzer_socket() {
  local analyzer_port="$1"

  stop_analyzer_mock
  (
    MOCK_PORT="${analyzer_port}" python3 - <<'PY'
import os
import socket

port = int(os.environ["MOCK_PORT"])

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen()
    while True:
        conn, _addr = server.accept()
        conn.close()
PY
  ) >"${TMP_DIR}/mock-analyzer-broken-socket.log" 2>&1 &
  ANALYZER_SESSION_PID="$!"
  sleep 1
}

build_sample_zip() {
  python3 - <<'PY' "${ROOT_DIR}" "${TMP_DIR}"
import sys
from pathlib import Path
from zipfile import ZipFile

root = Path(sys.argv[1])
tmp_dir = Path(sys.argv[2])
fixture_root = root / "tests" / "fixtures" / "input_bundle_spec_v1"
zip_path = tmp_dir / "input-bundle-spec-v1.zip"

with ZipFile(zip_path, "w") as zf:
    for file_path in sorted(fixture_root.rglob("*")):
        if file_path.is_file():
            zf.write(file_path, arcname=file_path.relative_to(fixture_root))

print(zip_path)
PY
}

run_upload() {
  local app_port="$1"
  local archive_path="$2"

  curl -sS -X POST "http://${APP_HOST}:${app_port}/api/tasks" \
    -F "file=@${archive_path}" \
    -F "parser_profile=default" \
    -F "report_lang=zh-CN" \
    -w $'\n%{http_code}'
}

verify_task_failure_state() {
  local app_port="$1"
  local task_id="$2"
  local expected_code="$3"
  local expected_message="$4"
  local expected_detail_key="${5:-}"
  local expected_detail_value="${6:-}"

  local task_response
  task_response="$(curl -fsS "http://${APP_HOST}:${app_port}/api/tasks/${task_id}")"

  python3 - <<'PY' "${task_response}" "${expected_code}" "${expected_message}" "${expected_detail_key}" "${expected_detail_value}"
import json
import sys

payload = json.loads(sys.argv[1])
expected_code = sys.argv[2]
expected_message = sys.argv[3]
expected_detail_key = sys.argv[4]
expected_detail_value = sys.argv[5]

data = payload["data"]
assert data["status"] == "analyze_failed", data["status"]
assert data["error"]["code"] == expected_code, data["error"]["code"]
assert data["error"]["message"] == expected_message, data["error"]["message"]

if expected_detail_key:
    actual = data["error"]["details"].get(expected_detail_key)
    assert str(actual) == expected_detail_value, (expected_detail_key, actual, expected_detail_value)

print(data["status"])
print(data["error"]["code"])
PY
}

verify_failure_response() {
  local response_json="$1"
  local expected_status_code="$2"
  local expected_code="$3"
  local expected_message="$4"
  local expected_detail_key="${5:-}"
  local expected_detail_value="${6:-}"

  python3 - <<'PY' "${response_json}" "${expected_status_code}" "${expected_code}" "${expected_message}" "${expected_detail_key}" "${expected_detail_value}"
import json
import sys

raw = sys.argv[1]
expected_status_code = sys.argv[2]
expected_code = sys.argv[3]
expected_message = sys.argv[4]
expected_detail_key = sys.argv[5]
expected_detail_value = sys.argv[6]

payload_text, status_code = raw.rsplit("\n", 1)
payload = json.loads(payload_text)

assert status_code == expected_status_code, status_code
assert payload["success"] is False
assert payload["error"]["code"] == expected_code, payload["error"]["code"]
assert payload["error"]["message"] == expected_message, payload["error"]["message"]

if expected_detail_key:
    actual = payload["error"]["details"].get(expected_detail_key)
    assert str(actual) == expected_detail_value, (expected_detail_key, actual, expected_detail_value)

print(payload["error"]["details"]["task_id"])
PY
}

verify_network_failure_response() {
  local response_json="$1"
  local expected_status_code="$2"
  local analyzer_base_url="$3"

  python3 - <<'PY' "${response_json}" "${expected_status_code}" "${analyzer_base_url}"
import json
import sys

raw = sys.argv[1]
expected_status_code = sys.argv[2]
analyzer_base_url = sys.argv[3]

payload_text, status_code = raw.rsplit("\n", 1)
payload = json.loads(payload_text)

assert status_code == expected_status_code, status_code
assert payload["success"] is False
assert payload["error"]["code"] in {
    "analyzer_unavailable",
    "analyzer_timeout",
    "analyzer_request_failed",
}, payload["error"]["code"]
assert analyzer_base_url in json.dumps(payload["error"]["details"], ensure_ascii=False)

print(payload["error"]["details"]["task_id"])
print(payload["error"]["code"])
print(payload["error"]["message"])
PY
}

verify_task_network_failure_state() {
  local app_port="$1"
  local task_id="$2"
  local analyzer_base_url="$3"

  local task_response
  task_response="$(curl -fsS "http://${APP_HOST}:${app_port}/api/tasks/${task_id}")"

  python3 - <<'PY' "${task_response}" "${analyzer_base_url}"
import json
import sys

payload = json.loads(sys.argv[1])
analyzer_base_url = sys.argv[2]

data = payload["data"]
assert data["status"] == "analyze_failed", data["status"]
assert data["error"]["code"] in {
    "analyzer_unavailable",
    "analyzer_timeout",
    "analyzer_request_failed",
}, data["error"]["code"]
assert analyzer_base_url in json.dumps(data["error"]["details"], ensure_ascii=False)
print(data["error"]["code"])
PY
}

run_unreachable_case() {
  local app_port
  local analyzer_port
  app_port="$(pick_free_port)"
  analyzer_port="$(pick_free_port)"

  step "Scenario: analyzer unavailable"
  start_broken_analyzer_socket "${analyzer_port}"
  start_platform "http://${ANALYZER_HOST}:${analyzer_port}" "${app_port}"

  local response_json
  response_json="$(run_upload "${app_port}" "${SAMPLE_ZIP}")"
  local verification_output
  verification_output="$(verify_network_failure_response \
    "${response_json}" \
    "503" \
    "http://${ANALYZER_HOST}:${analyzer_port}")"
  local task_id
  task_id="$(printf '%s\n' "${verification_output}" | sed -n '1p')"
  local actual_code
  actual_code="$(printf '%s\n' "${verification_output}" | sed -n '2p')"
  pass "Platform returned stable network-failure response (${actual_code})"

  actual_code="$(verify_task_network_failure_state \
    "${app_port}" \
    "${task_id}" \
    "http://${ANALYZER_HOST}:${analyzer_port}")"
  pass "Task detail retained analyze_failed and network-failure code (${actual_code})"
}

run_structured_case() {
  local scenario="$1"
  local app_port
  local analyzer_port
  local expected_code="$2"
  local expected_message="$3"
  local detail_key="$4"
  local detail_value="$5"
  app_port="$(pick_free_port)"
  analyzer_port="$(pick_free_port)"

  step "Scenario: structured analyzer error (${scenario})"
  start_analyzer_mock "${scenario}" "${analyzer_port}"
  start_platform "http://${ANALYZER_HOST}:${analyzer_port}" "${app_port}"

  local response_json
  response_json="$(run_upload "${app_port}" "${SAMPLE_ZIP}")"
  local task_id
  task_id="$(verify_failure_response \
    "${response_json}" \
    "503" \
    "${expected_code}" \
    "${expected_message}" \
    "${detail_key}" \
    "${detail_value}")"
  pass "Platform preserved structured analyzer error ${expected_code}"

  verify_task_failure_state \
    "${app_port}" \
    "${task_id}" \
    "${expected_code}" \
    "${expected_message}" \
    "${detail_key}" \
    "${detail_value}" >/dev/null
  pass "Task detail retained analyze_failed and ${expected_code}"
}

run_non_json_500_case() {
  local app_port
  local analyzer_port
  app_port="$(pick_free_port)"
  analyzer_port="$(pick_free_port)"

  step "Scenario: non-JSON analyzer 500"
  start_analyzer_mock "non_json_500" "${analyzer_port}"
  start_platform "http://${ANALYZER_HOST}:${analyzer_port}" "${app_port}"

  local response_json
  response_json="$(run_upload "${app_port}" "${SAMPLE_ZIP}")"
  local task_id
  task_id="$(verify_failure_response \
    "${response_json}" \
    "503" \
    "analyzer_request_failed" \
    "Analyzer service returned a non-success response." \
    "status_code" \
    "500")"
  pass "Platform returned stable fallback error for non-JSON 500"

  verify_task_failure_state \
    "${app_port}" \
    "${task_id}" \
    "analyzer_request_failed" \
    "Analyzer service returned a non-success response." \
    "content_type" \
    "text/plain" >/dev/null
  pass "Task detail retained analyze_failed and non-JSON fallback details"
}

step "Preparing failure-mode smoke test fixture"
TMP_DIR="$(mktemp -d)"
SAMPLE_ZIP="$(build_sample_zip)"
[[ -f "${SAMPLE_ZIP}" ]] || fail "Fixture archive was not created."
pass "Created sample archive ${SAMPLE_ZIP}"

run_unreachable_case
run_structured_case "unsupported_source_type" \
  "unsupported_source_type" \
  "Only directory source is supported in analyze-request/v1." \
  "source_type" \
  "archive"
run_structured_case "source_not_found" \
  "source_not_found" \
  "Requested source directory does not exist." \
  "path" \
  "/tmp/missing"
run_non_json_500_case

step "Remote analyzer failure verification completed"
echo "Scenarios verified:"
echo "- analyzer network failure path"
echo "- structured analyzer error: unsupported_source_type"
echo "- structured analyzer error: source_not_found"
echo "- non-JSON analyzer 500"
