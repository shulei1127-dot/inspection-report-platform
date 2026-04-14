# Log Analyzer API v1

## Goal

`log-analyzer-service` is a future standalone service that reads an already-extracted log directory and returns a versioned unified JSON result for the inspection-report platform.

This API exists to keep the service boundary explicit:

- the platform owns upload, archive persistence, extraction, task lifecycle, and report generation
- the analyzer owns log parsing and `UnifiedJsonV1` generation

The two services share protocol contracts, not internal Python module imports.

## Service Boundary

### Platform Responsibilities

- accept `.zip`, `.tar.gz`, and `.tgz`
- persist the uploaded archive
- extract the archive into `workdir/{task_id}/`
- call the analyzer service
- persist `unified.json`
- map unified JSON to `report_payload.json`
- trigger report rendering
- expose task detail, list, report download, and cleanup APIs

### Analyzer Responsibilities

- read a platform-prepared source directory
- parse supported log files
- produce a valid `UnifiedJsonV1`
- return analyzer metadata and warnings in a versioned response envelope

### Non-Goals For v1

- no archive upload to the analyzer service
- no task persistence inside the analyzer service
- no report payload generation
- no DOCX or PDF rendering
- no asynchronous job model
- no automatic retry orchestration

## Endpoints

### `GET /health`

Purpose:

- liveness and readiness check
- deployment validation
- platform-side startup and troubleshooting

Recommended success response:

```json
{
  "status": "ok",
  "service": "log-analyzer-service",
  "version": "0.1.0"
}
```

Notes:

- this response is intentionally small
- `version` should track analyzer service release version, not `schema_version`

### `POST /analyze`

Purpose:

- analyze one extracted log directory
- return one versioned `analyze-response/v1` envelope containing `UnifiedJsonV1`

## Versioning

Three version fields are used on purpose and should not be collapsed into one:

- `request_version`
  - request contract version
  - v1 value: `analyze-request/v1`
- `response_version`
  - outer response envelope version
  - v1 value: `analyze-response/v1`
- `schema_version`
  - inner unified result contract version
  - v1 value: `unified-json/v1`

Additionally:

- `analyzer_version`
  - identifies the analyzer implementation release
  - example: `0.1.0`

## Request Contract

### Top-Level Fields

Required:

- `request_version`
- `task_id`
- `source`

Optional:

- `archive_name`
- `archive_size_bytes`

### Request Shape

```json
{
  "request_version": "analyze-request/v1",
  "task_id": "tsk_20260413_123456_abcd1234",
  "source": {
    "type": "directory",
    "path": "/abs/path/to/workdir/tsk_20260413_123456_abcd1234"
  },
  "archive_name": "xray-collector.1776073884.tar.gz",
  "archive_size_bytes": 248193
}
```

### `source` Structure

The request keeps `source` as an extensible object from day one.

#### v1 Supported Source Type

Only this source type is supported in v1:

```json
{
  "type": "directory",
  "path": "/abs/path/to/workdir/tsk_xxx"
}
```

Field rules:

- `type`
  - required
  - must be `directory`
- `path`
  - required
  - absolute path to the extracted directory that the analyzer should read

### Why `source` Exists Instead Of `extracted_dir`

`source` is intentionally structured so the API can grow later without breaking request shape.

Future source types may include:

- `archive`
- `object_storage`
- `manifest`

These are not part of v1 and must not be implemented implicitly.

## Directory Source Convention v1

v1 requires the platform to pass a directory path that the analyzer process can read directly.

This means:

- platform and analyzer must share filesystem visibility for the provided path
- the analyzer should treat the given path as the analysis root
- the analyzer should not assume a fixed archive filename or upload transport

Recommended root example:

```text
/srv/inspection/workdir/tsk_20260413_123456_abcd1234
```

Inside that root, the current preferred input layout remains the canonical input bundle v1 structure:

```text
<analysis-root>/
  system/
    system_info
    systemctl_status
  containers/
    docker_ps
```

Notes:

- the analyzer may keep narrow fallback support for legacy file names internally
- the API contract only guarantees the root directory path, not every internal parser fallback

## Successful Response Contract

The analyzer must return a response envelope, not a bare `UnifiedJsonV1`.

### Top-Level Fields

Required:

- `response_version`
- `schema_version`
- `product_type`
- `analyzer_version`
- `analysis_started_at`
- `analysis_finished_at`
- `warnings`
- `result`

Optional:

- `input_summary`

### Response Shape

```json
{
  "response_version": "analyze-response/v1",
  "schema_version": "unified-json/v1",
  "product_type": "unknown",
  "analyzer_version": "0.1.0",
  "analysis_started_at": "2026-04-13T10:00:00Z",
  "analysis_finished_at": "2026-04-13T10:00:02Z",
  "warnings": [
    "Missing parser inputs fell back to defaults: systemctl_status."
  ],
  "input_summary": {
    "source_type": "directory",
    "path": "/abs/path/to/workdir/tsk_20260413_123456_abcd1234",
    "file_count": 42,
    "directory_count": 8
  },
  "result": {
    "schema_version": "unified-json/v1",
    "task_id": "tsk_20260413_123456_abcd1234",
    "generated_at": "2026-04-13T10:00:02Z",
    "source": {
      "archive_name": "xray-collector.1776073884.tar.gz",
      "archive_size_bytes": 248193,
      "collected_at": null
    },
    "parser": {
      "name": "default-linux-parser",
      "version": "0.5.0"
    },
    "host_info": {
      "hostname": "host-a",
      "ip": "10.0.0.8",
      "os_name": "Ubuntu",
      "os_version": "22.04.4 LTS",
      "kernel_version": "5.15.0-105-generic",
      "timezone": "Asia/Shanghai",
      "uptime_seconds": 93784,
      "last_boot_at": "2026-04-10T08:30:00Z"
    },
    "summary": {
      "overall_status": "warning",
      "service_count": 4,
      "service_running_count": 2,
      "container_count": 2,
      "container_running_count": 1,
      "issue_count": 3,
      "issue_by_severity": {
        "critical": 0,
        "high": 0,
        "medium": 2,
        "low": 1,
        "info": 0
      }
    },
    "services": [],
    "containers": [],
    "issues": [],
    "warnings": [],
    "metadata": {
      "extracted_file_count": 42,
      "extracted_directory_count": 8,
      "parsed_system_info": true,
      "parsed_systemctl_status": true,
      "parsed_docker_ps": true
    }
  }
}
```

`product_type` is the analyzer-side routing result for the requested source.

Current v1 values:

- `xray`
- `unknown`

### Response Rules

- `schema_version` at the envelope level must match the `result.schema_version`
- `analysis_started_at` and `analysis_finished_at` should use UTC ISO 8601
- `warnings` at the envelope level are analyzer-call warnings for this run
- `result.warnings` are still allowed because they are part of `UnifiedJsonV1`
- `input_summary` is optional but recommended

## Error Responses

The analyzer service should return structured JSON on failures.

Recommended error envelope:

```json
{
  "success": false,
  "error": {
    "code": "unsupported_source_type",
    "message": "Only directory source is supported in analyze-request/v1.",
    "details": {
      "source_type": "archive"
    }
  }
}
```

### Important Compatibility Note

The current platform-side `RemoteLogAnalyzer` implementation strictly depends on:

- `200` responses matching `AnalyzeResponseV1`
- non-`200` responses being treated as analyzer request failures

That means:

- rich non-`200` error bodies are recommended for humans and future integrations
- but platform v1 does not yet parse analyzer-side error envelopes into fine-grained task errors

## Recommended Error Codes

### Request Validation

- `invalid_request_version`
  - request version is missing or unsupported
- `unsupported_source_type`
  - `source.type` is not supported by v1
- `missing_source_path`
  - directory source path is missing
- `invalid_source_path`
  - path is malformed or not absolute

### Source Access

- `source_not_found`
  - provided directory does not exist
- `source_not_readable`
  - analyzer cannot read the directory
- `source_not_directory`
  - provided path exists but is not a directory

### Analysis Execution

- `analyze_timeout`
  - analysis exceeded the service-side timeout budget
- `analyze_internal_error`
  - unexpected analyzer-side failure
- `contract_generation_failed`
  - analyzer could not produce a valid `UnifiedJsonV1`

### Platform-Side Remote Adapter Errors

The current platform remote adapter may surface:

- `analyzer_timeout`
- `analyzer_unavailable`
- `analyzer_request_failed`
- `analyzer_invalid_response`

These are platform integration errors, not necessarily raw analyzer-service error codes.

## HTTP Status Recommendations

- `200`
  - successful analysis
- `400`
  - invalid request shape or unsupported version/type
- `404`
  - source path does not exist
- `422`
  - semantically valid JSON but invalid request content
- `500`
  - analyzer internal failure
- `503`
  - temporary analyzer-side unavailability if the service itself depends on unavailable components

## Timeout And Retry Contract

### Analyzer Service

The analyzer service should aim to complete within a bounded request timeout.

Recommended behavior:

- fail fast on unreadable or missing source paths
- do not hold requests open indefinitely
- return structured failures when analysis cannot complete

### Platform Caller

The current platform adapter uses:

- `ANALYZER_TIMEOUT_SECONDS`
- `ANALYZER_RETRY_COUNT`

Current recommended defaults:

```env
ANALYZER_TIMEOUT_SECONDS=30
ANALYZER_RETRY_COUNT=0
```

v1 behavior:

- timeout is mandatory
- automatic retries are optional and default to `0`
- retries should be limited to transport-level failures only

## Idempotency And Repeat Calls

v1 does not require the analyzer service to persist tasks or deduplicate requests.

Recommended interpretation:

- repeated `POST /analyze` calls with the same `task_id` are allowed
- the analyzer should treat each request as a fresh analysis run
- the platform remains responsible for deciding whether to overwrite previously stored `unified.json`

## Non-Target Scope For v1

The following are explicitly out of scope for this contract version:

- analyzer-managed archive upload
- analyzer-managed temporary extraction directories
- analyzer-managed cleanup of platform work directories
- report payload generation
- document rendering
- task list or task detail APIs inside the analyzer service
- asynchronous callback or webhook flows

## Relationship To Existing Contracts

- `result` must conform to `unified-json/v1`
- report generation in the platform must continue to use `report_payload.json`
- this API defines only the analyzer boundary, not the report rendering boundary

## Consistency Checklist

When implementing `log-analyzer-service`, verify:

- `POST /analyze` accepts `analyze-request/v1`
- only `source.type = "directory"` is accepted in v1
- successful responses return `analyze-response/v1`
- `result` validates as `UnifiedJsonV1`
- `schema_version` is `unified-json/v1`
- time fields use UTC ISO 8601 strings
- non-`200` failures return a structured JSON body
