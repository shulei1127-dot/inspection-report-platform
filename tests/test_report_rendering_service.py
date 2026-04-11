from pathlib import Path

import pytest

from app.schemas.report_payload import (
    ReportHost,
    ReportMeta,
    ReportPayloadV1,
    ReportSummary,
)
from app.services.report_rendering_service import (
    ReportRenderingError,
    maybe_render_report_from_payload_file,
    render_report_from_payload_file,
)


def test_render_service_requires_existing_report_payload(tmp_path: Path) -> None:
    template_path = tmp_path / "inspection_report.docx"
    template_path.write_bytes(b"fake-docx")

    with pytest.raises(ReportRenderingError) as exc_info:
        render_report_from_payload_file(
            "tsk_test_001",
            tmp_path / "missing_report_payload.json",
            template_path=template_path,
        )

    assert exc_info.value.code == "report_payload_missing"


def test_render_service_rejects_missing_template(tmp_path: Path) -> None:
    report_payload_path = _write_report_payload(tmp_path / "report_payload.json")

    with pytest.raises(ReportRenderingError) as exc_info:
        render_report_from_payload_file(
            "tsk_test_002",
            report_payload_path,
            template_path=tmp_path / "inspection_report.docx",
        )

    assert exc_info.value.code == "template_missing"


def test_upload_flow_stays_compatible_when_rendering_is_disabled(tmp_path: Path) -> None:
    report_payload_path = _write_report_payload(tmp_path / "report_payload.json")

    result = maybe_render_report_from_payload_file(
        "tsk_test_003",
        report_payload_path,
        enabled=False,
    )

    assert result.attempted is False
    assert result.success is False
    assert result.output_path is None
    assert result.error_code is None


def _write_report_payload(target_path: Path) -> Path:
    report_payload = ReportPayloadV1(
        payload_version="report-payload/v1",
        report=ReportMeta(
            title="Inspection Report",
            generated_at="2026-04-11T10:15:34Z",
            task_id="tsk_test_payload",
            report_lang="zh-CN",
        ),
        host=ReportHost(
            hostname="host-a",
            ip=None,
            os=None,
            kernel_version=None,
            timezone=None,
        ),
        summary=ReportSummary(
            overall_status="unknown",
            overall_status_label="Unknown",
            service_count=0,
            service_running_count=0,
            container_count=0,
            container_running_count=0,
            issue_count=0,
        ),
        service_rows=[],
        container_rows=[],
        issue_rows=[],
        highlights=["Upload completed."],
        recommendations=["Enable real rendering later."],
        appendix={"parser_name": "upload-parser-stub"},
    )
    target_path.write_text(
        report_payload.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return target_path
