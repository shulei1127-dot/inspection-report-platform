import shutil
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.schemas.tasks import (
    TaskCreateData,
    TaskCreateOptions,
    TaskError,
    TaskErrorResponse,
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
