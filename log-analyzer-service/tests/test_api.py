import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.analyze import AnalyzeResponseV1
from app.parsers import linux_default_parser


client = TestClient(app)
XRAY_FIXTURE_DIR = (
    Path(__file__).parent / "fixtures" / "xray_collector_v1" / "sample-bundle"
)


def test_get_health_returns_status_service_and_version() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "log-analyzer-service"
    assert payload["version"] == "0.1.0"


def test_post_analyze_happy_path_returns_versioned_response(tmp_path: Path) -> None:
    _write_supported_bundle(tmp_path)

    response = client.post(
        "/analyze",
        json={
            "request_version": "analyze-request/v1",
            "task_id": "tsk_analyzer_001",
            "source": {
                "type": "directory",
                "path": tmp_path.as_posix(),
            },
            "archive_name": "bundle.tar.gz",
            "archive_size_bytes": 1234,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    validated = AnalyzeResponseV1.model_validate(payload)

    assert validated.response_version == "analyze-response/v1"
    assert validated.schema_version == "unified-json/v1"
    assert validated.result.task_id == "tsk_analyzer_001"
    assert validated.result.host_info.hostname == "host-a"
    assert validated.result.summary.service_count == 1
    assert validated.result.summary.container_count == 1
    assert validated.input_summary is not None
    assert validated.input_summary.path == tmp_path.resolve().as_posix()
    assert validated.input_summary.file_count == 3
    assert validated.input_summary.directory_count == 2


def test_post_analyze_parses_docker_rows_when_ports_column_is_empty(tmp_path: Path) -> None:
    system_dir = tmp_path / "system"
    container_dir = tmp_path / "containers"
    system_dir.mkdir(parents=True)
    container_dir.mkdir(parents=True)

    (system_dir / "system_info").write_text(
        "\n".join(
            [
                "hostname=host-b",
                "kernel=5.15.0-test",
                "timezone=UTC",
                "uptime_seconds=1200",
                "last_boot_at=2026-04-13T08:00:00Z",
            ]
        ),
        encoding="utf-8",
    )
    (container_dir / "docker_ps").write_text(
        "\n".join(
            [
                "CONTAINER ID   IMAGE          COMMAND             CREATED        STATUS                  PORTS                 NAMES",
                'abc123         nginx:1.27     "/docker-entry"     3 months ago   Up 3 months (healthy)   0.0.0.0:443->443/tcp  xray-nginx',
                'def456         app:latest     "bash deploy.sh"    3 months ago   Up 3 months (healthy)                         xray-deploy',
                'ghi789         app:latest     "bash run.sh"       3 months ago   Exited (1) 2 hours ago                         xray-web',
            ]
        ),
        encoding="utf-8",
    )

    response = client.post(
        "/analyze",
        json={
            "request_version": "analyze-request/v1",
            "task_id": "tsk_analyzer_docker_empty_ports",
            "source": {
                "type": "directory",
                "path": tmp_path.as_posix(),
            },
        },
    )

    assert response.status_code == 200
    validated = AnalyzeResponseV1.model_validate(response.json())

    assert validated.result.summary.container_count == 3
    assert [container.name for container in validated.result.containers] == [
        "xray-nginx",
        "xray-deploy",
        "xray-web",
    ]
    assert any(issue.related_object_name == "xray-web" for issue in validated.result.issues)


def test_post_analyze_recognizes_xray_collector_input(tmp_path: Path) -> None:
    xray_root = tmp_path / "xray-collector.20260413123039"
    shutil.copytree(XRAY_FIXTURE_DIR, xray_root)

    response = client.post(
        "/analyze",
        json={
            "request_version": "analyze-request/v1",
            "task_id": "tsk_analyzer_xray_001",
            "source": {
                "type": "directory",
                "path": tmp_path.as_posix(),
            },
            "archive_name": "xray-collector.20260413123039.tar.gz",
            "archive_size_bytes": 4096,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    validated = AnalyzeResponseV1.model_validate(payload)

    assert validated.result.task_id == "tsk_analyzer_xray_001"
    assert validated.result.parser is not None
    assert validated.result.parser.name == "xray-collector-parser"
    assert validated.result.host_info.hostname == "24waf"
    assert validated.result.host_info.ip == "10.10.20.30"
    assert validated.result.host_info.timezone == "Etc/UTC"
    assert validated.result.host_info.last_boot_at == "2026-03-22T05:08:48Z"
    assert validated.result.summary.overall_status == "warning"
    assert validated.result.summary.service_count == 2
    assert validated.result.summary.container_count == 3
    assert validated.result.summary.issue_count == 2
    assert [service.name for service in validated.result.services] == [
        "fwupd-refresh",
        "minion",
    ]
    assert any(service.name == "minion" and service.status == "running" for service in validated.result.services)
    assert any(service.name == "fwupd-refresh" and service.status == "failed" for service in validated.result.services)
    assert validated.result.containers[0].name == "xray-nginx"
    assert any(container.name == "xray-upgrader" for container in validated.result.containers)
    assert any(container.name == "xray-gunkit-base" for container in validated.result.containers)
    assert validated.result.metadata["collector_type"] == "xray-collector/v1"
    assert any("xray-collector v1 input detected" in warning for warning in validated.warnings)


def test_post_analyze_rejects_unsupported_source_type(tmp_path: Path) -> None:
    response = client.post(
        "/analyze",
        json={
            "request_version": "analyze-request/v1",
            "task_id": "tsk_analyzer_bad_source",
            "source": {
                "type": "archive",
                "path": tmp_path.as_posix(),
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "success": False,
        "error": {
            "code": "unsupported_source_type",
            "message": "Only directory source is supported in analyze-request/v1.",
            "details": {
                "source_type": "archive",
            },
        },
    }


def test_post_analyze_returns_source_not_found_for_missing_directory() -> None:
    response = client.post(
        "/analyze",
        json={
            "request_version": "analyze-request/v1",
            "task_id": "tsk_analyzer_missing_dir",
            "source": {
                "type": "directory",
                "path": "/tmp/definitely-missing-analyzer-dir",
            },
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {
            "code": "source_not_found",
            "message": "Requested source directory does not exist.",
            "details": {
                "path": "/tmp/definitely-missing-analyzer-dir",
            },
        },
    }


def test_post_analyze_returns_analyzer_internal_error_when_parser_crashes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_supported_bundle(tmp_path)

    def explode(self, **kwargs):  # noqa: ANN001, ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(linux_default_parser.LinuxDefaultParser, "parse", explode)

    response = client.post(
        "/analyze",
        json={
            "request_version": "analyze-request/v1",
            "task_id": "tsk_analyzer_internal_error",
            "source": {
                "type": "directory",
                "path": tmp_path.as_posix(),
            },
        },
    )

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "error": {
            "code": "analyzer_internal_error",
            "message": "Analyzer failed to process the requested directory.",
            "details": {
                "task_id": "tsk_analyzer_internal_error",
            },
        },
    }


def _write_supported_bundle(root_dir: Path) -> None:
    system_dir = root_dir / "system"
    container_dir = root_dir / "containers"
    system_dir.mkdir(parents=True)
    container_dir.mkdir(parents=True)

    (system_dir / "system_info").write_text(
        "\n".join(
            [
                "hostname=host-a",
                "pretty_name=Ubuntu 22.04 LTS",
                "kernel=5.15.0-105-generic",
                "timezone=UTC",
                "uptime_seconds=7200",
                "ip=10.0.0.8",
                "last_boot_at=2026-04-13T08:00:00Z",
            ]
        ),
        encoding="utf-8",
    )
    (system_dir / "systemctl_status").write_text(
        "UNIT LOAD ACTIVE SUB DESCRIPTION\n"
        "nginx.service loaded active running A high performance web server\n",
        encoding="utf-8",
    )
    (container_dir / "docker_ps").write_text(
        "NAMES\tIMAGE\tSTATUS\tPORTS\n"
        "api\tnginx:1.27\tUp 5 minutes\t0.0.0.0:8080->80/tcp\n",
        encoding="utf-8",
    )
