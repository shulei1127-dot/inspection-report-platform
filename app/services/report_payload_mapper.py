from pathlib import Path

from app.schemas.report_payload import (
    ContainerRow,
    IssueRow,
    ReportHost,
    ReportMeta,
    ReportPayloadV1,
    ReportSummary,
    ServiceRow,
)
from app.schemas.unified_json import UnifiedJsonV1


OVERALL_STATUS_LABELS = {
    "healthy": "Healthy",
    "warning": "Warning",
    "critical": "Critical",
    "unknown": "Unknown",
}

RUNTIME_STATUS_LABELS = {
    "running": "Running",
    "stopped": "Stopped",
    "failed": "Failed",
    "unknown": "Unknown",
}

ISSUE_SEVERITY_LABELS = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "info": "Info",
}


def map_unified_json_to_report_payload(
    unified_json: UnifiedJsonV1,
    *,
    report_lang: str = "zh-CN",
) -> ReportPayloadV1:
    host_os = _join_parts(
        [
            unified_json.host_info.os_name,
            unified_json.host_info.os_version,
        ]
    )

    return ReportPayloadV1(
        payload_version="report-payload/v1",
        report=ReportMeta(
            title="Inspection Report",
            generated_at=unified_json.generated_at,
            task_id=unified_json.task_id,
            report_lang=report_lang,
        ),
        host=ReportHost(
            hostname=unified_json.host_info.hostname,
            ip=unified_json.host_info.ip,
            os=host_os,
            kernel_version=unified_json.host_info.kernel_version,
            timezone=unified_json.host_info.timezone,
        ),
        summary=ReportSummary(
            overall_status=unified_json.summary.overall_status,
            overall_status_label=OVERALL_STATUS_LABELS[unified_json.summary.overall_status],
            service_count=unified_json.summary.service_count,
            service_running_count=unified_json.summary.service_running_count,
            container_count=unified_json.summary.container_count,
            container_running_count=unified_json.summary.container_running_count,
            issue_count=unified_json.summary.issue_count,
        ),
        service_rows=[
            ServiceRow(
                name=service.display_name or service.name,
                status=service.status,
                status_label=RUNTIME_STATUS_LABELS[service.status],
                enabled=_format_bool(service.enabled),
                version=service.version or "-",
                ports=", ".join(str(port) for port in service.listen_ports) or "-",
                notes=service.notes or "-",
            )
            for service in unified_json.services
        ],
        container_rows=[
            ContainerRow(
                name=container.name,
                image=container.image or "-",
                status=container.status,
                status_label=RUNTIME_STATUS_LABELS[container.status],
                ports=", ".join(container.ports) or "-",
                notes=container.notes or "-",
            )
            for container in unified_json.containers
        ],
        issue_rows=[
            IssueRow(
                id=issue.id,
                severity=issue.severity,
                severity_label=ISSUE_SEVERITY_LABELS[issue.severity],
                category=issue.category,
                title=issue.title,
                description=issue.description or "-",
                suggestion=issue.suggestion or "-",
            )
            for issue in unified_json.issues
        ],
        highlights=_build_highlights(unified_json),
        recommendations=_build_recommendations(unified_json),
        appendix=_build_appendix(unified_json),
    )


def persist_report_payload(report_payload: ReportPayloadV1, target_path: Path) -> None:
    target_path.write_text(
        report_payload.model_dump_json(indent=2),
        encoding="utf-8",
    )


def _format_bool(value: bool | None) -> str:
    if value is None:
        return "-"
    return "Yes" if value else "No"


def _join_parts(parts: list[str | None]) -> str | None:
    values = [part for part in parts if part]
    if not values:
        return None
    return " ".join(values)


def _build_highlights(unified_json: UnifiedJsonV1) -> list[str]:
    return [
        f"Upload task {unified_json.task_id} completed and unified JSON was generated.",
    ]


def _build_recommendations(unified_json: UnifiedJsonV1) -> list[str]:
    parser_name = unified_json.parser.name if unified_json.parser else "unknown-parser"
    return [
        f"Review results produced by {parser_name} and continue expanding parser coverage for additional log types.",
    ]


def _build_appendix(unified_json: UnifiedJsonV1) -> dict[str, str | int | float | bool | None]:
    parser_name = unified_json.parser.name if unified_json.parser else None
    parser_version = unified_json.parser.version if unified_json.parser else None

    appendix: dict[str, str | int | float | bool | None] = {
        "parser_name": parser_name,
        "parser_version": parser_version,
    }

    if "extracted_file_count" in unified_json.metadata:
        appendix["extracted_file_count"] = unified_json.metadata["extracted_file_count"]

    return appendix
