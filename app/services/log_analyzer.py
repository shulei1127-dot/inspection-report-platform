from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.log_analyzer import (
    AnalyzeInputSummary,
    AnalyzeRequestV1,
    AnalyzeResponseV1,
)
from app.services.parser_stub import build_unified_json


class LogAnalyzerError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, str | int | float | bool | None] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class LogAnalyzer(Protocol):
    def analyze(self, request: AnalyzeRequestV1) -> AnalyzeResponseV1: ...


@dataclass(frozen=True)
class LocalLogAnalyzer:
    analyzer_version: str = "0.1.0"

    def analyze(self, request: AnalyzeRequestV1) -> AnalyzeResponseV1:
        extracted_dir = Path(request.source.path)
        analysis_started_at = _utc_now_iso()
        unified_json = build_unified_json(
            request.task_id,
            extracted_dir,
            archive_name=request.archive_name,
            archive_size_bytes=request.archive_size_bytes,
        )
        analysis_finished_at = _utc_now_iso()

        return AnalyzeResponseV1(
            analyzer_version=self.analyzer_version,
            analysis_started_at=analysis_started_at,
            analysis_finished_at=analysis_finished_at,
            warnings=list(unified_json.warnings),
            input_summary=AnalyzeInputSummary(
                path=request.source.path,
                file_count=int(unified_json.metadata.get("extracted_file_count", 0)),
                directory_count=int(unified_json.metadata.get("extracted_directory_count", 0)),
            ),
            result=unified_json,
        )


@dataclass(frozen=True)
class RemoteLogAnalyzer:
    base_url: str
    timeout_seconds: float
    retry_count: int = 0
    transport: httpx.BaseTransport | None = None

    def analyze(self, request: AnalyzeRequestV1) -> AnalyzeResponseV1:
        attempts = max(self.retry_count, 0) + 1
        last_error: LogAnalyzerError | None = None

        for _ in range(attempts):
            try:
                return self._send_request(request)
            except LogAnalyzerError as exc:
                last_error = exc
                if exc.code not in {"analyzer_timeout", "analyzer_unavailable"}:
                    raise

        if last_error is not None:
            raise last_error

        raise LogAnalyzerError(
            code="analyzer_unavailable",
            message="Analyzer request failed before any response was received.",
        )

    def _send_request(self, request: AnalyzeRequestV1) -> AnalyzeResponseV1:
        timeout = httpx.Timeout(self.timeout_seconds)
        payload = request.model_dump(mode="json")

        try:
            with httpx.Client(timeout=timeout, transport=self.transport) as client:
                response = client.post(
                    f"{self.base_url.rstrip('/')}/analyze",
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise LogAnalyzerError(
                code="analyzer_timeout",
                message="Analyzer request timed out.",
                details={"analyzer_base_url": self.base_url},
            ) from exc
        except httpx.HTTPError as exc:
            raise LogAnalyzerError(
                code="analyzer_unavailable",
                message="Failed to reach the analyzer service.",
                details={"analyzer_base_url": self.base_url},
            ) from exc

        if response.status_code != 200:
            raise LogAnalyzerError(
                code="analyzer_request_failed",
                message="Analyzer service returned a non-success response.",
                details={
                    "analyzer_base_url": self.base_url,
                    "status_code": response.status_code,
                    "response_excerpt": response.text[:300] or None,
                },
            )

        try:
            return AnalyzeResponseV1.model_validate(response.json())
        except (ValidationError, ValueError) as exc:
            raise LogAnalyzerError(
                code="analyzer_invalid_response",
                message="Analyzer response did not match the expected contract.",
                details={"analyzer_base_url": self.base_url},
            ) from exc


def build_log_analyzer() -> LogAnalyzer:
    settings = get_settings()
    if settings.analyzer_mode == "remote":
        return RemoteLogAnalyzer(
            base_url=settings.analyzer_base_url,
            timeout_seconds=settings.analyzer_timeout_seconds,
            retry_count=settings.analyzer_retry_count,
        )
    return LocalLogAnalyzer()


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
