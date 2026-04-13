# Analyzer Test Plan

The first real implementation of `log-analyzer-service` should include at least:

- `GET /health` returns `200`
- `POST /analyze` returns a valid `analyze-response/v1`
- nonexistent directory returns a structured error
- unsupported `source.type` returns a structured error
- successful responses validate against the analyzer-side response model
