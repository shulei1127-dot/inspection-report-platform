import shutil
import uuid
import zipfile
from datetime import UTC, datetime
from json import JSONDecodeError
from pathlib import Path

from fastapi import UploadFile
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.unified_json import UnifiedJsonV1
from app.schemas.tasks import (
    TaskCreateData,
    TaskCreateOptions,
    TaskDeleteData,
    TaskError,
    TaskErrorResponse,
    TaskResultData,
    TaskSummary,
)
from app.services.parser_stub import build_unified_json, persist_unified_json
from app.services.report_payload_mapper import (
    map_unified_json_to_report_payload,
    persist_report_payload,
)
from app.services.report_rendering_service import maybe_render_report_from_payload_file


class TaskUploadError(Exception):
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

    def to_response(self) -> TaskErrorResponse:
        return TaskErrorResponse(
            error=TaskError(
                code=self.code,
                message=self.message,
                details=self.details,
            )
        )


class TaskLookupError(Exception):
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

    def to_response(self) -> TaskErrorResponse:
        return TaskErrorResponse(
            error=TaskError(
                code=self.code,
                message=self.message,
                details=self.details,
            )
        )


def create_task_from_upload(upload: UploadFile | None, options: TaskCreateOptions) -> TaskCreateData:
    if upload is None:
        raise TaskUploadError(
            status_code=400,
            code="missing_file",
            message="No upload file was provided.",
        )

    filename = upload.filename or ""
    if not filename:
        raise TaskUploadError(
            status_code=400,
            code="missing_file",
            message="No upload file was provided.",
        )

    if not filename.lower().endswith(".zip"):
        raise TaskUploadError(
            status_code=415,
            code="unsupported_media_type",
            message="Only .zip files are accepted.",
            details={"filename": filename},
        )

    settings = get_settings()
    task_id = generate_task_id()
    zip_path = settings.uploads_dir / f"{task_id}.zip"
    task_workdir = settings.workdir_dir / task_id
    unified_json_path = task_workdir / "unified.json"
    report_payload_path = task_workdir / "report_payload.json"
    report_file_path: str | None = None

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    task_workdir.mkdir(parents=True, exist_ok=True)

    try:
        _save_upload(upload, zip_path)
        _validate_zip_file(zip_path, filename)
        _extract_zip_archive(zip_path, task_workdir, filename)
        unified_json = build_unified_json(
            task_id,
            task_workdir,
            archive_name=filename,
            archive_size_bytes=zip_path.stat().st_size,
        )
        persist_unified_json(unified_json, unified_json_path)
        report_payload = map_unified_json_to_report_payload(
            unified_json,
            report_lang=options.report_lang,
        )
        persist_report_payload(report_payload, report_payload_path)
        render_result = maybe_render_report_from_payload_file(
            task_id,
            report_payload_path,
        )
        if render_result.success and render_result.output_path is not None:
            report_file_path = render_result.output_path.as_posix()
    except TaskUploadError:
        _cleanup_failed_task(zip_path, task_workdir)
        raise
    except OSError as exc:
        _cleanup_failed_task(zip_path, task_workdir)
        raise TaskUploadError(
            status_code=500,
            code="internal_error",
            message="Failed to persist the uploaded task files.",
            details={"filename": filename, "reason": str(exc)},
        ) from exc

    return TaskCreateData(
        task_id=task_id,
        status="completed",
        filename=filename,
        parser_profile=options.parser_profile,
        report_lang=options.report_lang,
        stored_zip_path=zip_path.as_posix(),
        workdir_path=task_workdir.as_posix(),
        unified_json_path=unified_json_path.as_posix(),
        report_payload_path=report_payload_path.as_posix(),
        report_file_path=report_file_path,
        summary=TaskSummary(
            service_count=unified_json.summary.service_count,
            container_count=unified_json.summary.container_count,
            issue_count=unified_json.summary.issue_count,
        ),
    )


def generate_task_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"tsk_{timestamp}_{suffix}"


def get_task_result(task_id: str) -> TaskResultData:
    artifact_paths = _resolve_task_paths(task_id)
    _ensure_task_exists(task_id, artifact_paths=artifact_paths)
    summary = _load_task_summary(artifact_paths["unified_json_path"])
    status = _derive_task_status(
        unified_json_path=artifact_paths["unified_json_path"],
        report_payload_path=artifact_paths["report_payload_path"],
        report_file_path=artifact_paths["report_file_path"],
    )

    return TaskResultData(
        task_id=task_id,
        status=status,
        created_at=_derive_task_created_at(task_id, artifact_paths=artifact_paths),
        unified_json_path=(
            artifact_paths["unified_json_path"].as_posix()
            if artifact_paths["unified_json_path"].exists()
            else None
        ),
        report_payload_path=(
            artifact_paths["report_payload_path"].as_posix()
            if artifact_paths["report_payload_path"].exists()
            else None
        ),
        report_file_path=(
            artifact_paths["report_file_path"].as_posix()
            if artifact_paths["report_file_path"].exists()
            else None
        ),
        summary=summary,
    )


def list_task_results() -> list[TaskResultData]:
    settings = get_settings()
    task_ids = _discover_task_ids(
        uploads_dir=settings.uploads_dir,
        workdir_dir=settings.workdir_dir,
        outputs_dir=settings.outputs_dir,
    )

    task_results = [get_task_result(task_id) for task_id in task_ids]
    task_results.sort(
        key=lambda result: _task_sort_key(result),
        reverse=True,
    )
    return task_results


def get_task_report_path(task_id: str) -> Path:
    report_file_path = _resolve_task_paths(task_id)["report_file_path"]
    if not report_file_path.exists():
        raise TaskLookupError(
            status_code=404,
            code="report_not_found",
            message="Rendered report file does not exist.",
            details={"task_id": task_id},
        )
    return report_file_path


def delete_task(task_id: str) -> TaskDeleteData:
    artifact_paths = _resolve_task_paths(task_id)
    _ensure_task_exists(task_id, artifact_paths=artifact_paths)

    deleted_paths: list[str] = []

    stored_zip_path = artifact_paths["stored_zip_path"]
    if stored_zip_path.exists():
        stored_zip_path.unlink()
        deleted_paths.append(stored_zip_path.as_posix())

    task_workdir = artifact_paths["task_workdir"]
    if task_workdir.exists():
        shutil.rmtree(task_workdir)
        deleted_paths.append(task_workdir.as_posix())

    outputs_dir = artifact_paths["outputs_task_dir"]
    if outputs_dir.exists():
        shutil.rmtree(outputs_dir)
        deleted_paths.append(outputs_dir.as_posix())

    return TaskDeleteData(
        task_id=task_id,
        deleted=True,
        deleted_paths=deleted_paths,
    )


def _save_upload(upload: UploadFile, target_path: Path) -> None:
    upload.file.seek(0)
    with target_path.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    upload.file.seek(0)


def _validate_zip_file(zip_path: Path, filename: str) -> None:
    if not zipfile.is_zipfile(zip_path):
        raise TaskUploadError(
            status_code=400,
            code="invalid_zip",
            message="The uploaded file is not a valid zip archive.",
            details={"filename": filename},
        )


def _extract_zip_archive(zip_path: Path, target_dir: Path, filename: str) -> None:
    root = target_dir.resolve()

    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                destination = (target_dir / member.filename).resolve()
                if destination != root and root not in destination.parents:
                    raise TaskUploadError(
                        status_code=500,
                        code="extract_failed",
                        message="Failed to extract the uploaded zip archive.",
                        details={"filename": filename, "reason": "unsafe_archive_path"},
                    )

            archive.extractall(target_dir)
    except TaskUploadError:
        raise
    except zipfile.BadZipFile as exc:
        raise TaskUploadError(
            status_code=400,
            code="invalid_zip",
            message="The uploaded file is not a valid zip archive.",
            details={"filename": filename},
        ) from exc
    except OSError as exc:
        raise TaskUploadError(
            status_code=500,
            code="extract_failed",
            message="Failed to extract the uploaded zip archive.",
            details={"filename": filename, "reason": str(exc)},
        ) from exc


def _cleanup_failed_task(zip_path: Path, task_workdir: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    if task_workdir.exists():
        shutil.rmtree(task_workdir)


def _load_task_summary(unified_json_path: Path) -> TaskSummary:
    if not unified_json_path.exists():
        return TaskSummary()

    try:
        unified_json = UnifiedJsonV1.model_validate_json(
            unified_json_path.read_text(encoding="utf-8")
        )
    except (OSError, JSONDecodeError, ValidationError):
        return TaskSummary()

    return TaskSummary(
        service_count=unified_json.summary.service_count,
        container_count=unified_json.summary.container_count,
        issue_count=unified_json.summary.issue_count,
    )


def _resolve_task_paths(task_id: str) -> dict[str, Path]:
    settings = get_settings()
    task_workdir = settings.workdir_dir / task_id
    outputs_task_dir = settings.outputs_dir / task_id
    return {
        "stored_zip_path": settings.uploads_dir / f"{task_id}.zip",
        "task_workdir": task_workdir,
        "unified_json_path": task_workdir / "unified.json",
        "report_payload_path": task_workdir / "report_payload.json",
        "outputs_task_dir": outputs_task_dir,
        "report_file_path": outputs_task_dir / "report.docx",
    }


def _ensure_task_exists(task_id: str, *, artifact_paths: dict[str, Path]) -> None:
    if not any(path.exists() for path in artifact_paths.values()):
        raise TaskLookupError(
            status_code=404,
            code="task_not_found",
            message="Task result does not exist.",
            details={"task_id": task_id},
        )


def _derive_task_status(
    *,
    unified_json_path: Path,
    report_payload_path: Path,
    report_file_path: Path,
) -> str:
    if report_file_path.exists():
        return "rendered"
    if unified_json_path.exists() and report_payload_path.exists():
        return "completed"
    return "processing"


def _derive_task_created_at(task_id: str, *, artifact_paths: dict[str, Path]) -> str | None:
    parsed_from_task_id = _parse_created_at_from_task_id(task_id)
    if parsed_from_task_id is not None:
        return parsed_from_task_id

    mtimes = [
        path.stat().st_mtime
        for path in artifact_paths.values()
        if path.exists()
    ]
    if not mtimes:
        return None

    latest_mtime = max(mtimes)
    return (
        datetime.fromtimestamp(latest_mtime, tz=UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_created_at_from_task_id(task_id: str) -> str | None:
    parts = task_id.split("_")
    if len(parts) < 4 or parts[0] != "tsk":
        return None

    timestamp = f"{parts[1]}_{parts[2]}"
    try:
        parsed = datetime.strptime(timestamp, "%Y%m%d_%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None
    return parsed.isoformat().replace("+00:00", "Z")


def _discover_task_ids(
    *,
    uploads_dir: Path,
    workdir_dir: Path,
    outputs_dir: Path,
) -> list[str]:
    task_ids: set[str] = set()

    if uploads_dir.exists():
        for path in uploads_dir.glob("tsk_*.zip"):
            task_ids.add(path.stem)

    if workdir_dir.exists():
        for path in workdir_dir.iterdir():
            if path.is_dir() and path.name.startswith("tsk_"):
                task_ids.add(path.name)

    if outputs_dir.exists():
        for path in outputs_dir.iterdir():
            if path.is_dir() and path.name.startswith("tsk_"):
                task_ids.add(path.name)

    return sorted(task_ids)


def _task_sort_key(task_result: TaskResultData) -> tuple[str, str]:
    return (task_result.created_at or "", task_result.task_id)
