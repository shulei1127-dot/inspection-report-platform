# log-analyzer-service

`log-analyzer-service` is the planned standalone parser service for the inspection report platform.

This subdirectory is intentionally a minimal standalone implementation, not a full analyzer feature set.

## Purpose

The service will own:

- reading a platform-prepared extracted directory
- parsing supported log inputs
- generating `UnifiedJsonV1`
- returning `analyze-response/v1`

The service will not own:

- archive upload
- archive extraction
- task history persistence
- report payload generation
- DOCX or PDF rendering

## Current Status

This subtree currently provides:

- project directory structure
- configuration module
- real `GET /health`
- analyzer request/response models
- real `POST /analyze` happy path for `source.type=directory`
- structured error handling for unsupported source types and missing directories
- parser and service layer implementation for the current migrated parser scope

Current implemented parser coverage:

- `system_info`
- `systemctl_status`
- `docker_ps`

Still intentionally out of scope:

- archive upload
- asynchronous jobs
- persistence
- parser expansion beyond the current migrated coverage

## Recommended Structure

```text
log-analyzer-service/
  app/
    api/
      endpoints/
      router.py
    core/
      config.py
    schemas/
      analyze.py
      health.py
    services/
      analyzer_service.py
    parsers/
      linux_default_parser.py
    main.py
  tests/
  .env.example
  requirements.txt
```

## Layer Responsibilities

### `app/api/`

- define HTTP routes
- validate request and response boundaries
- convert service exceptions into HTTP responses

### `app/schemas/`

- define versioned analyzer request and response models
- define health response models
- define analyzer-local unified JSON models
- keep analyzer-side contract models independent from platform internal imports

### `app/services/`

- implement analyzer orchestration
- validate source mode and directory accessibility
- invoke parser modules
- return `AnalyzeResponseV1`

### `app/parsers/`

- hold parser implementations
- host migration targets for the current platform parser behavior
- keep parsing logic independent from HTTP concerns

### `app/core/`

- hold configuration loading
- service name, version, host, port, timeouts, and source-mode flags

### `app/main.py`

- build the FastAPI application
- include the API router

## Suggested v1 Configuration

- `ANALYZER_APP_NAME`
- `ANALYZER_APP_HOST`
- `ANALYZER_APP_PORT`
- `ANALYZER_VERSION`
- `ANALYZE_TIMEOUT_SECONDS`
- `ALLOW_DIRECTORY_SOURCE`

## Parser Migration Strategy

Phase 1:

- copy the current parser capability into this service
- start with the current `system_info`, `systemctl_status`, and `docker_ps` handling
- keep issue generation logic functionally equivalent

Phase 2:

- move helper functions out of platform naming
- split parser code into parser-focused modules under `app/parsers/`
- keep service orchestration in `app/services/`

Phase 3:

- expand collectors and parser coverage only after the standalone boundary is stable

## Current Minimal Test Set

- `GET /health` returns `200`
- `POST /analyze` returns a valid `analyze-response/v1`
- nonexistent directory returns structured error
- unsupported `source.type` returns structured error
- parser crash path returns `analyzer_internal_error`
- successful responses validate as `AnalyzeResponseV1`

## Contract Reference

Implementation should follow:

- [docs/log_analyzer_api_v1.md](../docs/log_analyzer_api_v1.md)
