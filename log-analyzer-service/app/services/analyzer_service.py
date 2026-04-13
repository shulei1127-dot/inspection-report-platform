from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.parsers.linux_default_parser import LinuxDefaultParser
from app.parsers.xray_collector_parser import XrayCollectorParser
from app.schemas.analyze import (
    AnalyzeInputSummary,
    AnalyzeRequestV1,
    AnalyzeResponseV1,
)


class AnalyzerServiceError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, str | int | float | bool | None] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class AnalyzerService:
    analyzer_version: str
    allow_directory_source: bool

    def analyze(self, request: AnalyzeRequestV1) -> AnalyzeResponseV1:
        analysis_started_at = _utc_now_iso()
        analysis_root = self._resolve_analysis_root(request)

        try:
            file_count, directory_count = _scan_analysis_root(analysis_root)
            unified_json = self._parse_analysis_root(
                task_id=request.task_id,
                analysis_root=analysis_root,
                archive_name=request.archive_name,
                archive_size_bytes=request.archive_size_bytes,
            )
        except AnalyzerServiceError:
            raise
        except Exception as exc:
            raise AnalyzerServiceError(
                status_code=500,
                code="analyzer_internal_error",
                message="Analyzer failed to process the requested directory.",
                details={"task_id": request.task_id},
            ) from exc

        analysis_finished_at = _utc_now_iso()
        return AnalyzeResponseV1(
            analyzer_version=self.analyzer_version,
            analysis_started_at=analysis_started_at,
            analysis_finished_at=analysis_finished_at,
            warnings=list(unified_json.warnings),
            input_summary=AnalyzeInputSummary(
                source_type="directory",
                path=analysis_root.as_posix(),
                file_count=file_count,
                directory_count=directory_count,
            ),
            result=unified_json,
        )

    def _resolve_analysis_root(self, request: AnalyzeRequestV1) -> Path:
        source_type = request.source.type.strip().lower()
        if source_type != "directory":
            raise AnalyzerServiceError(
                status_code=400,
                code="unsupported_source_type",
                message="Only directory source is supported in analyze-request/v1.",
                details={"source_type": request.source.type},
            )

        if not self.allow_directory_source:
            raise AnalyzerServiceError(
                status_code=400,
                code="unsupported_source_type",
                message="Directory source is disabled by analyzer configuration.",
                details={"source_type": request.source.type},
            )

        source_path = (request.source.path or "").strip()
        if not source_path:
            raise AnalyzerServiceError(
                status_code=400,
                code="invalid_source_path",
                message="Directory source path is required.",
                details={"source_type": request.source.type},
            )

        analysis_root = Path(source_path)
        if not analysis_root.exists():
            raise AnalyzerServiceError(
                status_code=404,
                code="source_not_found",
                message="Requested source directory does not exist.",
                details={"path": source_path},
            )

        if not analysis_root.is_dir():
            raise AnalyzerServiceError(
                status_code=400,
                code="source_not_directory",
                message="Requested source path is not a directory.",
                details={"path": source_path},
            )

        return analysis_root.resolve()

    def _parse_analysis_root(
        self,
        *,
        task_id: str,
        analysis_root: Path,
        archive_name: str | None,
        archive_size_bytes: int | None,
    ):
        xray_parser = XrayCollectorParser()
        if xray_parser.detect(analysis_root) is not None:
            return xray_parser.parse(
                task_id=task_id,
                analysis_root=analysis_root,
                archive_name=archive_name,
                archive_size_bytes=archive_size_bytes,
            )

        return LinuxDefaultParser().parse(
            task_id=task_id,
            analysis_root=analysis_root,
            archive_name=archive_name,
            archive_size_bytes=archive_size_bytes,
        )


def build_analyzer_service() -> AnalyzerService:
    settings = get_settings()
    return AnalyzerService(
        analyzer_version=settings.analyzer_version,
        allow_directory_source=settings.allow_directory_source,
    )


def _scan_analysis_root(analysis_root: Path) -> tuple[int, int]:
    file_count = 0
    directory_count = 0

    for path in analysis_root.rglob("*"):
        if path.is_file():
            file_count += 1
        elif path.is_dir():
            directory_count += 1

    return file_count, directory_count


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
