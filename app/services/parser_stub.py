from datetime import UTC, datetime
from pathlib import Path

from app.schemas.unified_json import (
    HostInfo,
    IssueBySeverity,
    UnifiedJsonParser,
    UnifiedJsonSource,
    UnifiedJsonSummary,
    UnifiedJsonV1,
)


def build_unified_json_stub(
    task_id: str,
    extracted_dir: Path,
    *,
    archive_name: str | None = None,
    archive_size_bytes: int | None = None,
) -> UnifiedJsonV1:
    file_count, dir_count = _scan_extracted_dir(extracted_dir)
    hostname = _derive_hostname(extracted_dir, archive_name)

    return UnifiedJsonV1(
        schema_version="unified-json/v1",
        task_id=task_id,
        generated_at=_utc_now_isoformat(),
        source=UnifiedJsonSource(
            archive_name=archive_name,
            archive_size_bytes=archive_size_bytes,
            collected_at=None,
        ),
        parser=UnifiedJsonParser(
            name="upload-parser-stub",
            version="0.1.0",
        ),
        host_info=HostInfo(
            hostname=hostname,
            ip=None,
            os_name=None,
            os_version=None,
            kernel_version=None,
            timezone=None,
            uptime_seconds=None,
            last_boot_at=None,
        ),
        summary=UnifiedJsonSummary(
            overall_status="unknown",
            service_count=0,
            service_running_count=0,
            container_count=0,
            container_running_count=0,
            issue_count=0,
            issue_by_severity=IssueBySeverity(
                critical=0,
                high=0,
                medium=0,
                low=0,
                info=0,
            ),
        ),
        services=[],
        containers=[],
        issues=[],
        warnings=[
            "Parser stub used; real log parsing is not implemented yet.",
        ],
        metadata={
            "extracted_file_count": file_count,
            "extracted_directory_count": dir_count,
        },
    )


def persist_unified_json(unified_json: UnifiedJsonV1, target_path: Path) -> None:
    target_path.write_text(
        unified_json.model_dump_json(indent=2),
        encoding="utf-8",
    )


def _scan_extracted_dir(extracted_dir: Path) -> tuple[int, int]:
    file_count = 0
    dir_count = 0

    for path in extracted_dir.rglob("*"):
        if path.is_file():
            file_count += 1
        elif path.is_dir():
            dir_count += 1

    return file_count, dir_count


def _derive_hostname(extracted_dir: Path, archive_name: str | None) -> str:
    if archive_name:
        stem = Path(archive_name).stem.strip()
        if stem:
            return stem

    top_level_dirs = sorted(
        path.name
        for path in extracted_dir.iterdir()
        if path.is_dir() and path.name.strip()
    )
    if len(top_level_dirs) == 1:
        return top_level_dirs[0]

    top_level_files = sorted(
        path.stem
        for path in extracted_dir.iterdir()
        if path.is_file() and path.stem.strip()
    )
    if len(top_level_files) == 1:
        return top_level_files[0]

    return "unknown-host"


def _utc_now_isoformat() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
