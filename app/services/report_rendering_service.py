from dataclasses import dataclass, field
from json import JSONDecodeError
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.report_payload import ReportPayloadV1


class ReportRenderingError(Exception):
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


@dataclass(frozen=True)
class ReportRenderResult:
    attempted: bool
    success: bool
    output_path: Path | None = None
    error_code: str | None = None
    error_message: str | None = None
    details: dict[str, str | int | float | bool | None] = field(default_factory=dict)


class ReportRendererAdapter(Protocol):
    def render(
        self,
        *,
        template_path: Path,
        report_payload: ReportPayloadV1,
        output_path: Path,
    ) -> None: ...


class UnavailableCarboneAdapter:
    def render(
        self,
        *,
        template_path: Path,
        report_payload: ReportPayloadV1,
        output_path: Path,
    ) -> None:
        raise ReportRenderingError(
            code="carbone_unavailable",
            message="Carbone runtime is not configured in the current environment.",
            details={
                "template_path": template_path.as_posix(),
                "output_path": output_path.as_posix(),
            },
        )


def maybe_render_report_from_payload_file(
    task_id: str,
    report_payload_path: Path,
    *,
    enabled: bool | None = None,
    template_path: Path | None = None,
    output_path: Path | None = None,
    adapter: ReportRendererAdapter | None = None,
) -> ReportRenderResult:
    settings = get_settings()
    render_enabled = settings.report_rendering_enabled if enabled is None else enabled

    if not render_enabled:
        return ReportRenderResult(attempted=False, success=False)

    try:
        rendered_output_path = render_report_from_payload_file(
            task_id,
            report_payload_path,
            template_path=template_path,
            output_path=output_path,
            adapter=adapter,
        )
    except ReportRenderingError as exc:
        return ReportRenderResult(
            attempted=True,
            success=False,
            error_code=exc.code,
            error_message=exc.message,
            details=exc.details,
        )

    return ReportRenderResult(
        attempted=True,
        success=True,
        output_path=rendered_output_path,
    )


def render_report_from_payload_file(
    task_id: str,
    report_payload_path: Path,
    *,
    template_path: Path | None = None,
    output_path: Path | None = None,
    adapter: ReportRendererAdapter | None = None,
) -> Path:
    report_payload = _load_report_payload(report_payload_path)

    settings = get_settings()
    resolved_template_path = template_path or settings.default_report_template_path
    if not resolved_template_path.exists():
        raise ReportRenderingError(
            code="template_missing",
            message="Report template file does not exist.",
            details={"template_path": resolved_template_path.as_posix()},
        )

    resolved_output_path = output_path or settings.outputs_dir / task_id / "report.docx"
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_adapter = adapter or build_report_renderer_adapter()
    resolved_adapter.render(
        template_path=resolved_template_path,
        report_payload=report_payload,
        output_path=resolved_output_path,
    )

    return resolved_output_path


def build_report_renderer_adapter() -> ReportRendererAdapter:
    return UnavailableCarboneAdapter()


def _load_report_payload(report_payload_path: Path) -> ReportPayloadV1:
    if not report_payload_path.exists():
        raise ReportRenderingError(
            code="report_payload_missing",
            message="Report payload file does not exist.",
            details={"report_payload_path": report_payload_path.as_posix()},
        )

    try:
        return ReportPayloadV1.model_validate_json(
            report_payload_path.read_text(encoding="utf-8")
        )
    except (OSError, JSONDecodeError, ValidationError) as exc:
        raise ReportRenderingError(
            code="invalid_report_payload",
            message="Report payload file is invalid or cannot be parsed.",
            details={"report_payload_path": report_payload_path.as_posix()},
        ) from exc
