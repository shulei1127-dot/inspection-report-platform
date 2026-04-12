import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.report_payload import ReportPayloadV1
from app.schemas.unified_json import UnifiedJsonV1


client = TestClient(app)
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "real_parser_v1"
SPEC_V1_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "input_bundle_spec_v1"


def test_get_task_returns_minimal_result_for_existing_task(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    create_response = client.post(
        "/api/tasks",
        files={"file": ("host-a-logs.zip", _build_zip_bytes({"system.log": "ok\n"}), "application/zip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )
    assert create_response.status_code == 201

    task_id = create_response.json()["data"]["task_id"]

    response = client.get(f"/api/tasks/{task_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["task_id"] == task_id
    assert payload["data"]["status"] == "completed"
    assert payload["data"]["created_at"] is not None
    assert payload["data"]["unified_json_path"] == f"workdir/{task_id}/unified.json"
    assert payload["data"]["report_payload_path"] == f"workdir/{task_id}/report_payload.json"
    assert payload["data"]["report_file_path"] is None
    assert payload["data"]["summary"]["issue_count"] == 4


def test_list_tasks_returns_multiple_items_in_latest_first_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    _write_task_files(
        tmp_path,
        task_id="tsk_20260412_010101_older001",
        summary={"service_count": 1, "container_count": 0, "issue_count": 0},
        include_report=False,
    )
    _write_task_files(
        tmp_path,
        task_id="tsk_20260412_030303_latest03",
        summary={"service_count": 2, "container_count": 1, "issue_count": 1},
        include_report=True,
    )
    _write_task_files(
        tmp_path,
        task_id="tsk_20260412_020202_middle02",
        summary={"service_count": 1, "container_count": 1, "issue_count": 0},
        include_report=False,
    )

    response = client.get("/api/tasks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert [item["task_id"] for item in payload["data"]] == [
        "tsk_20260412_030303_latest03",
        "tsk_20260412_020202_middle02",
        "tsk_20260412_010101_older001",
    ]
    assert payload["data"][0]["status"] == "rendered"
    assert payload["data"][0]["report_file_path"] == (
        "outputs/tsk_20260412_030303_latest03/report.docx"
    )
    assert payload["data"][0]["created_at"] == "2026-04-12T03:03:03Z"
    assert payload["data"][1]["summary"] == {
        "service_count": 1,
        "container_count": 1,
        "issue_count": 0,
    }
    assert payload["data"][2]["unified_json_path"] == (
        "workdir/tsk_20260412_010101_older001/unified.json"
    )


def test_get_task_report_downloads_existing_docx(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    task_id = "tsk_test_report_download"
    report_dir = tmp_path / "outputs" / task_id
    report_dir.mkdir(parents=True)
    report_path = report_dir / "report.docx"
    report_bytes = _build_docx_bytes("Report content")
    report_path.write_bytes(report_bytes)

    response = client.get(f"/api/tasks/{task_id}/report")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "attachment;" in response.headers["content-disposition"]
    assert f'{task_id}.docx' in response.headers["content-disposition"]
    assert response.content == report_bytes


def test_get_task_report_returns_404_when_report_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    response = client.get("/api/tasks/tsk_missing_report/report")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {
            "code": "report_not_found",
            "message": "Rendered report file does not exist.",
            "details": {
                "task_id": "tsk_missing_report",
            },
        },
    }


def test_delete_task_removes_task_artifacts_and_followup_queries_fail(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    task_id = "tsk_20260412_050505_delete01"
    _write_task_files(
        tmp_path,
        task_id=task_id,
        summary={"service_count": 1, "container_count": 1, "issue_count": 1},
        include_report=True,
    )

    delete_response = client.delete(f"/api/tasks/{task_id}")

    assert delete_response.status_code == 200
    payload = delete_response.json()
    assert payload["success"] is True
    assert payload["data"]["task_id"] == task_id
    assert payload["data"]["deleted"] is True
    assert payload["data"]["deleted_paths"] == [
        f"uploads/{task_id}.zip",
        f"workdir/{task_id}",
        f"outputs/{task_id}",
    ]

    assert not (tmp_path / "uploads" / f"{task_id}.zip").exists()
    assert not (tmp_path / "workdir" / task_id).exists()
    assert not (tmp_path / "outputs" / task_id).exists()

    get_task_response = client.get(f"/api/tasks/{task_id}")
    assert get_task_response.status_code == 404
    assert get_task_response.json()["error"]["code"] == "task_not_found"

    download_response = client.get(f"/api/tasks/{task_id}/report")
    assert download_response.status_code == 404
    assert download_response.json()["error"]["code"] == "report_not_found"


def test_delete_task_returns_404_when_task_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    response = client.delete("/api/tasks/tsk_missing_delete")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {
            "code": "task_not_found",
            "message": "Task result does not exist.",
            "details": {
                "task_id": "tsk_missing_delete",
            },
        },
    }


def test_create_task_parses_supported_files_into_unified_json_and_report_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    zip_bytes = _build_zip_bytes(
        {
            fixture_path.name: fixture_path.read_text(encoding="utf-8")
            for fixture_path in sorted(FIXTURE_DIR.iterdir())
        }
    )

    response = client.post(
        "/api/tasks",
        files={"file": ("real-parser-v1.zip", zip_bytes, "application/zip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 201

    payload = response.json()
    task_id = payload["data"]["task_id"]
    unified_json_path = tmp_path / "workdir" / task_id / "unified.json"
    report_payload_path = tmp_path / "workdir" / task_id / "report_payload.json"

    assert payload["data"]["summary"] == {
        "service_count": 4,
        "container_count": 2,
        "issue_count": 3,
    }
    assert unified_json_path.exists()
    assert report_payload_path.exists()

    unified_json = UnifiedJsonV1.model_validate_json(
        unified_json_path.read_text(encoding="utf-8")
    )
    report_payload = ReportPayloadV1.model_validate_json(
        report_payload_path.read_text(encoding="utf-8")
    )

    assert unified_json.host_info.hostname == "host-a"
    assert unified_json.host_info.ip == "10.0.0.8"
    assert unified_json.host_info.os_name == "Ubuntu"
    assert unified_json.host_info.kernel_version == "5.15.0-105-generic"
    assert unified_json.host_info.timezone == "Asia/Shanghai"
    assert unified_json.host_info.uptime_seconds == 93784
    assert unified_json.host_info.last_boot_at == "2026-04-10T08:30:00Z"
    assert [service.name for service in unified_json.services] == [
        "nginx",
        "docker",
        "fail2ban",
        "auditd",
    ]
    assert [container.name for container in unified_json.containers] == [
        "redis",
        "worker",
    ]
    assert unified_json.summary.service_count == 4
    assert unified_json.summary.container_count == 2
    assert unified_json.summary.issue_count == 3
    assert unified_json.summary.overall_status == "warning"
    assert unified_json.parser is not None
    assert unified_json.parser.name == "default-linux-parser"
    assert [issue.id for issue in unified_json.issues] == [
        "service-fail2ban-failed",
        "service-auditd-inactive",
        "container-worker-exited",
    ]

    assert report_payload.host.hostname == "host-a"
    assert report_payload.host.os == "Ubuntu 22.04.4 LTS (Jammy Jellyfish)"
    assert report_payload.summary.overall_status == "warning"
    assert report_payload.summary.service_count == 4
    assert report_payload.summary.container_count == 2
    assert report_payload.summary.issue_count == 3
    assert [row.name for row in report_payload.service_rows] == [
        "A high performance web server",
        "Docker Application Container Engine",
        "Fail2Ban Service",
        "Security Auditing Service",
    ]
    assert [row.name for row in report_payload.container_rows] == ["redis", "worker"]
    assert [row.id for row in report_payload.issue_rows] == [
        "service-fail2ban-failed",
        "service-auditd-inactive",
        "container-worker-exited",
    ]
    assert report_payload.appendix["parser_name"] == "default-linux-parser"


def test_create_task_parses_input_bundle_spec_v1_layout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    zip_bytes = _build_zip_bytes(
        {
            str(fixture_path.relative_to(SPEC_V1_FIXTURE_DIR)): fixture_path.read_text(encoding="utf-8")
            for fixture_path in sorted(path for path in SPEC_V1_FIXTURE_DIR.rglob("*") if path.is_file())
        }
    )

    response = client.post(
        "/api/tasks",
        files={"file": ("spec-v1.zip", zip_bytes, "application/zip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 201
    payload = response.json()
    task_id = payload["data"]["task_id"]
    unified_json = UnifiedJsonV1.model_validate_json(
        (tmp_path / "workdir" / task_id / "unified.json").read_text(encoding="utf-8")
    )

    assert unified_json.host_info.hostname == "host-a"
    assert unified_json.summary.service_count == 4
    assert unified_json.summary.container_count == 2


def test_create_task_uploads_extracts_zip_and_writes_contract_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    zip_bytes = _build_zip_bytes(
        {
            "logs/system.log": "system ok\n",
            "meta/info.txt": "metadata\n",
        }
    )

    response = client.post(
        "/api/tasks",
        files={"file": ("host-a-logs.zip", zip_bytes, "application/zip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 201

    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["status"] == "completed"
    assert payload["data"]["contract_version"] == "task-response/v1"
    assert payload["data"]["filename"] == "host-a-logs.zip"
    assert payload["data"]["parser_profile"] == "default"
    assert payload["data"]["report_lang"] == "zh-CN"
    assert payload["data"]["summary"] == {
        "service_count": 0,
        "container_count": 0,
        "issue_count": 4,
    }
    assert payload["data"]["report_file_path"] is None

    task_id = payload["data"]["task_id"]
    stored_zip_path = tmp_path / "uploads" / f"{task_id}.zip"
    unified_json_path = tmp_path / "workdir" / task_id / "unified.json"
    report_payload_path = tmp_path / "workdir" / task_id / "report_payload.json"
    extracted_log_path = tmp_path / "workdir" / task_id / "logs" / "system.log"
    extracted_info_path = tmp_path / "workdir" / task_id / "meta" / "info.txt"

    assert stored_zip_path.exists()
    assert payload["data"]["unified_json_path"] == f"workdir/{task_id}/unified.json"
    assert payload["data"]["report_payload_path"] == f"workdir/{task_id}/report_payload.json"
    assert unified_json_path.exists()
    assert report_payload_path.exists()
    assert extracted_log_path.read_text() == "system ok\n"
    assert extracted_info_path.read_text() == "metadata\n"

    unified_json_data = json.loads(unified_json_path.read_text(encoding="utf-8"))
    unified_json = UnifiedJsonV1.model_validate(unified_json_data)

    assert unified_json.schema_version == "unified-json/v1"
    assert unified_json.task_id == task_id
    assert unified_json.host_info.hostname == "host-a-logs"
    assert unified_json.summary.overall_status == "warning"
    assert unified_json.summary.service_count == 0
    assert unified_json.summary.container_count == 0
    assert unified_json.summary.issue_count == 4
    assert unified_json.services == []
    assert unified_json.containers == []
    assert [issue.id for issue in unified_json.issues] == [
        "host-hostname-missing",
        "host-kernel-version-missing",
        "host-timezone-missing",
        "host-uptime-missing",
    ]
    assert unified_json.parser is not None
    assert unified_json.parser.name == "default-linux-parser"
    assert unified_json.source is not None
    assert unified_json.source.archive_name == "host-a-logs.zip"
    assert unified_json.metadata["extracted_file_count"] == 2

    report_payload_data = json.loads(report_payload_path.read_text(encoding="utf-8"))
    report_payload = ReportPayloadV1.model_validate(report_payload_data)

    assert report_payload.payload_version == "report-payload/v1"
    assert report_payload.report.task_id == task_id
    assert report_payload.report.report_lang == "zh-CN"
    assert report_payload.host.hostname == "host-a-logs"
    assert report_payload.summary.overall_status == "warning"
    assert report_payload.summary.overall_status_label == "Warning"
    assert report_payload.service_rows == []
    assert report_payload.container_rows == []
    assert [row.id for row in report_payload.issue_rows] == [
        "host-hostname-missing",
        "host-kernel-version-missing",
        "host-timezone-missing",
        "host-uptime-missing",
    ]
    assert report_payload.highlights == [
        f"Upload task {task_id} completed and unified JSON was generated.",
    ]
    assert report_payload.recommendations == [
        "Review results produced by default-linux-parser and continue expanding parser coverage for additional log types.",
    ]
    assert report_payload.appendix["parser_name"] == "default-linux-parser"
    assert report_payload.appendix["extracted_file_count"] == 2


def test_create_task_rejects_non_zip_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/tasks",
        files={"file": ("notes.txt", b"not a zip", "text/plain")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 415
    assert response.json() == {
        "success": False,
        "error": {
            "code": "unsupported_media_type",
            "message": "Only .zip files are accepted.",
            "details": {
                "filename": "notes.txt",
            },
        },
    }


def test_create_task_requires_file_field(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/tasks",
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "success": False,
        "error": {
            "code": "missing_file",
            "message": "No upload file was provided.",
            "details": {},
        },
    }


def _build_zip_bytes(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)

    return buffer.getvalue()


def _build_docx_bytes(document_text: str) -> bytes:
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "")
        archive.writestr("word/document.xml", document_text)

    return buffer.getvalue()


def _write_task_files(
    root_dir: Path,
    *,
    task_id: str,
    summary: dict[str, int],
    include_report: bool,
) -> None:
    workdir = root_dir / "workdir" / task_id
    outputs_dir = root_dir / "outputs" / task_id
    uploads_dir = root_dir / "uploads"
    workdir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    (uploads_dir / f"{task_id}.zip").write_bytes(b"zip")

    unified_json = {
        "schema_version": "unified-json/v1",
        "task_id": task_id,
        "generated_at": "2026-04-12T00:00:00Z",
        "host_info": {
            "hostname": "host-a",
            "ip": None,
            "os_name": None,
            "os_version": None,
            "kernel_version": None,
            "timezone": None,
            "uptime_seconds": None,
            "last_boot_at": None,
        },
        "summary": {
            "overall_status": "warning" if summary["issue_count"] else "healthy",
            "service_count": summary["service_count"],
            "service_running_count": summary["service_count"],
            "container_count": summary["container_count"],
            "container_running_count": summary["container_count"],
            "issue_count": summary["issue_count"],
            "issue_by_severity": {
                "critical": 0,
                "high": 0,
                "medium": summary["issue_count"],
                "low": 0,
                "info": 0,
            },
        },
        "services": [],
        "containers": [],
        "issues": [],
        "warnings": [],
        "metadata": {},
    }

    report_payload = {
        "payload_version": "report-payload/v1",
        "report": {
            "title": "Inspection Report",
            "generated_at": "2026-04-12T00:00:00Z",
            "task_id": task_id,
            "report_lang": "zh-CN",
        },
        "host": {
            "hostname": "host-a",
            "ip": None,
            "os": None,
            "kernel_version": None,
            "timezone": None,
        },
        "summary": {
            "overall_status": "warning" if summary["issue_count"] else "healthy",
            "overall_status_label": "Warning" if summary["issue_count"] else "Healthy",
            "service_count": summary["service_count"],
            "service_running_count": summary["service_count"],
            "container_count": summary["container_count"],
            "container_running_count": summary["container_count"],
            "issue_count": summary["issue_count"],
        },
        "service_rows": [],
        "container_rows": [],
        "issue_rows": [],
        "highlights": [],
        "recommendations": [],
        "appendix": {},
    }

    (workdir / "unified.json").write_text(json.dumps(unified_json), encoding="utf-8")
    (workdir / "report_payload.json").write_text(
        json.dumps(report_payload),
        encoding="utf-8",
    )

    if include_report:
        (outputs_dir / "report.docx").write_bytes(_build_docx_bytes("Report content"))
