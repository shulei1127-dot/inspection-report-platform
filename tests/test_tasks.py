import io
import json
import sqlite3
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.report_payload import ReportPayloadV1
from app.schemas.unified_json import UnifiedJsonV1
from app.services.log_analyzer import LocalLogAnalyzer, LogAnalyzerError, RemoteLogAnalyzer
from app.services.report_rendering_service import ReportRenderResult
from app.services import task_service


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
    task_row = _fetch_task_db_row(tmp_path, task_id)

    response = client.get(f"/api/tasks/{task_id}")

    assert task_row is not None
    assert task_row["status"] == "completed"
    assert task_row["archive_path"] == f"uploads/{task_id}.zip"
    assert task_row["workdir_path"] == f"workdir/{task_id}"
    assert task_row["unified_json_path"] == f"workdir/{task_id}/unified.json"
    assert task_row["report_payload_path"] == f"workdir/{task_id}/report_payload.json"
    assert task_row["report_file_path"] is None
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["task_id"] == task_id
    assert payload["data"]["status"] == "completed"
    assert payload["data"]["created_at"] == task_row["created_at"]
    assert payload["data"]["unified_json_path"] == f"workdir/{task_id}/unified.json"
    assert payload["data"]["report_payload_path"] == f"workdir/{task_id}/report_payload.json"
    assert payload["data"]["report_file_path"] is None
    assert payload["data"]["summary"]["issue_count"] == 4


def test_create_task_accepts_tar_gz_archive_and_extracts_supported_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    tar_gz_bytes = _build_tar_gz_bytes(
        {
            "system/system_info": (
                'hostname=tar-host\nPRETTY_NAME="Ubuntu 24.04 LTS"\n'
                "kernel=6.8.0\ntimezone=UTC\nuptime=7200\nip=10.0.0.21\n"
                "last_boot_at=2026-04-12T00:00:00Z\n"
            ),
            "system/systemctl_status": (
                "UNIT LOAD ACTIVE SUB DESCRIPTION\n"
                "nginx.service loaded active running A high performance web server\n"
            ),
            "containers/docker_ps": (
                "NAMES\tIMAGE\tSTATUS\tPORTS\n"
                "api\tnginx:1.27\tUp 15 minutes\t0.0.0.0:8080->80/tcp\n"
            ),
        }
    )

    response = client.post(
        "/api/tasks",
        files={"file": ("host-a-inspection.tar.gz", tar_gz_bytes, "application/gzip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 201
    payload = response.json()
    task_id = payload["data"]["task_id"]
    task_row = _fetch_task_db_row(tmp_path, task_id)
    unified_json_path = tmp_path / "workdir" / task_id / "unified.json"

    assert payload["data"]["filename"] == "host-a-inspection.tar.gz"
    assert payload["data"]["stored_zip_path"] == f"uploads/{task_id}.tar.gz"
    assert task_row is not None
    assert task_row["archive_path"] == f"uploads/{task_id}.tar.gz"
    assert (tmp_path / "uploads" / f"{task_id}.tar.gz").exists()

    unified_json = UnifiedJsonV1.model_validate_json(
        unified_json_path.read_text(encoding="utf-8")
    )
    assert unified_json.host_info.hostname == "tar-host"
    assert unified_json.summary.service_count == 1
    assert unified_json.summary.container_count == 1


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
    _write_task_db_row(
        tmp_path,
        task_id="tsk_20260412_010101_older001",
        status="completed",
        created_at="2026-04-12T01:01:01Z",
        updated_at="2026-04-12T01:01:01Z",
        archive_path="uploads/tsk_20260412_010101_older001.zip",
        workdir_path="workdir/tsk_20260412_010101_older001",
        unified_json_path="workdir/tsk_20260412_010101_older001/unified.json",
        report_payload_path="workdir/tsk_20260412_010101_older001/report_payload.json",
        report_file_path=None,
    )
    _write_task_files(
        tmp_path,
        task_id="tsk_20260412_030303_latest03",
        summary={"service_count": 2, "container_count": 1, "issue_count": 1},
        include_report=True,
    )
    _write_task_db_row(
        tmp_path,
        task_id="tsk_20260412_030303_latest03",
        status="rendered",
        created_at="2026-04-12T03:03:03Z",
        updated_at="2026-04-12T03:03:03Z",
        archive_path="uploads/tsk_20260412_030303_latest03.zip",
        workdir_path="workdir/tsk_20260412_030303_latest03",
        unified_json_path="workdir/tsk_20260412_030303_latest03/unified.json",
        report_payload_path="workdir/tsk_20260412_030303_latest03/report_payload.json",
        report_file_path="outputs/tsk_20260412_030303_latest03/report.docx",
    )
    _write_task_files(
        tmp_path,
        task_id="tsk_20260412_020202_middle02",
        summary={"service_count": 1, "container_count": 1, "issue_count": 0},
        include_report=False,
    )
    _write_task_db_row(
        tmp_path,
        task_id="tsk_20260412_020202_middle02",
        status="completed",
        created_at="2026-04-12T02:02:02Z",
        updated_at="2026-04-12T02:02:02Z",
        archive_path="uploads/tsk_20260412_020202_middle02.zip",
        workdir_path="workdir/tsk_20260412_020202_middle02",
        unified_json_path="workdir/tsk_20260412_020202_middle02/unified.json",
        report_payload_path="workdir/tsk_20260412_020202_middle02/report_payload.json",
        report_file_path=None,
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


def test_get_task_prefers_database_record_when_available(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    task_id = "tsk_20260412_080808_dbfirst01"
    _write_task_files(
        tmp_path,
        task_id=task_id,
        summary={"service_count": 1, "container_count": 1, "issue_count": 0},
        include_report=False,
    )
    _write_task_db_row(
        tmp_path,
        task_id=task_id,
        status="analyze_failed",
        created_at="2026-04-12T08:08:08Z",
        updated_at="2026-04-12T08:09:09Z",
        archive_path=f"uploads/{task_id}.zip",
        workdir_path=f"workdir/{task_id}",
        unified_json_path=f"workdir/{task_id}/unified.json",
        report_payload_path=f"workdir/{task_id}/report_payload.json",
        report_file_path=None,
        error_code="extract_failed",
        error_message="synthetic failure for database-priority test",
        error_details='{"filename":"bundle.zip","reason":"synthetic"}',
    )

    response = client.get(f"/api/tasks/{task_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["task_id"] == task_id
    assert payload["data"]["status"] == "analyze_failed"
    assert payload["data"]["created_at"] == "2026-04-12T08:08:08Z"
    assert payload["data"]["error"] == {
        "code": "extract_failed",
        "message": "synthetic failure for database-priority test",
        "details": {
            "filename": "bundle.zip",
            "reason": "synthetic",
        },
    }
    assert payload["data"]["summary"] == {
        "service_count": 1,
        "container_count": 1,
        "issue_count": 0,
    }


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
    assert _fetch_task_db_row(tmp_path, task_id) is None

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


def test_cleanup_tasks_keep_latest_removes_older_safe_tasks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    _write_task_files(
        tmp_path,
        task_id="tsk_20260413_010101_oldest01",
        summary={"service_count": 1, "container_count": 0, "issue_count": 0},
        include_report=False,
    )
    _write_task_db_row(
        tmp_path,
        task_id="tsk_20260413_010101_oldest01",
        status="completed",
        created_at="2026-04-13T01:01:01Z",
        updated_at="2026-04-13T01:01:01Z",
        archive_path="uploads/tsk_20260413_010101_oldest01.zip",
        workdir_path="workdir/tsk_20260413_010101_oldest01",
        unified_json_path="workdir/tsk_20260413_010101_oldest01/unified.json",
        report_payload_path="workdir/tsk_20260413_010101_oldest01/report_payload.json",
        report_file_path=None,
    )
    _write_task_files(
        tmp_path,
        task_id="tsk_20260413_020202_middle02",
        summary={"service_count": 1, "container_count": 1, "issue_count": 1},
        include_report=True,
    )
    _write_task_db_row(
        tmp_path,
        task_id="tsk_20260413_020202_middle02",
        status="rendered",
        created_at="2026-04-13T02:02:02Z",
        updated_at="2026-04-13T02:02:02Z",
        archive_path="uploads/tsk_20260413_020202_middle02.zip",
        workdir_path="workdir/tsk_20260413_020202_middle02",
        unified_json_path="workdir/tsk_20260413_020202_middle02/unified.json",
        report_payload_path="workdir/tsk_20260413_020202_middle02/report_payload.json",
        report_file_path="outputs/tsk_20260413_020202_middle02/report.docx",
    )
    _write_task_files(
        tmp_path,
        task_id="tsk_20260413_030303_latest03",
        summary={"service_count": 2, "container_count": 0, "issue_count": 0},
        include_report=False,
    )
    _write_task_db_row(
        tmp_path,
        task_id="tsk_20260413_030303_latest03",
        status="completed",
        created_at="2026-04-13T03:03:03Z",
        updated_at="2026-04-13T03:03:03Z",
        archive_path="uploads/tsk_20260413_030303_latest03.zip",
        workdir_path="workdir/tsk_20260413_030303_latest03",
        unified_json_path="workdir/tsk_20260413_030303_latest03/unified.json",
        report_payload_path="workdir/tsk_20260413_030303_latest03/report_payload.json",
        report_file_path=None,
    )

    response = client.post("/api/tasks/cleanup", json={"keep_latest": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"] == {
        "scanned_count": 3,
        "deleted_count": 2,
        "skipped_count": 1,
        "deleted_task_ids": [
            "tsk_20260413_020202_middle02",
            "tsk_20260413_010101_oldest01",
        ],
    }

    assert _fetch_task_db_row(tmp_path, "tsk_20260413_030303_latest03") is not None
    assert (tmp_path / "workdir" / "tsk_20260413_030303_latest03").exists()

    assert _fetch_task_db_row(tmp_path, "tsk_20260413_020202_middle02") is None
    assert _fetch_task_db_row(tmp_path, "tsk_20260413_010101_oldest01") is None
    assert not (tmp_path / "workdir" / "tsk_20260413_020202_middle02").exists()
    assert not (tmp_path / "workdir" / "tsk_20260413_010101_oldest01").exists()
    assert not (tmp_path / "outputs" / "tsk_20260413_020202_middle02").exists()


def test_cleanup_tasks_older_than_days_skips_analyzing_and_recent_tasks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        task_service,
        "_utc_now",
        lambda: datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC),
    )

    _write_task_files(
        tmp_path,
        task_id="tsk_20260410_010101_olddone01",
        summary={"service_count": 1, "container_count": 0, "issue_count": 0},
        include_report=False,
    )
    _write_task_db_row(
        tmp_path,
        task_id="tsk_20260410_010101_olddone01",
        status="completed",
        created_at="2026-04-10T01:01:01Z",
        updated_at="2026-04-10T01:01:01Z",
        archive_path="uploads/tsk_20260410_010101_olddone01.zip",
        workdir_path="workdir/tsk_20260410_010101_olddone01",
        unified_json_path="workdir/tsk_20260410_010101_olddone01/unified.json",
        report_payload_path="workdir/tsk_20260410_010101_olddone01/report_payload.json",
        report_file_path=None,
    )
    _write_task_files(
        tmp_path,
        task_id="tsk_20260410_020202_oldproc02",
        summary={"service_count": 1, "container_count": 1, "issue_count": 0},
        include_report=False,
    )
    _write_task_db_row(
        tmp_path,
        task_id="tsk_20260410_020202_oldproc02",
        status="analyzing",
        created_at="2026-04-10T02:02:02Z",
        updated_at="2026-04-10T02:02:02Z",
        archive_path="uploads/tsk_20260410_020202_oldproc02.zip",
        workdir_path="workdir/tsk_20260410_020202_oldproc02",
        unified_json_path="workdir/tsk_20260410_020202_oldproc02/unified.json",
        report_payload_path="workdir/tsk_20260410_020202_oldproc02/report_payload.json",
        report_file_path=None,
    )
    _write_task_files(
        tmp_path,
        task_id="tsk_20260412_030303_recent03",
        summary={"service_count": 2, "container_count": 1, "issue_count": 0},
        include_report=True,
    )
    _write_task_db_row(
        tmp_path,
        task_id="tsk_20260412_030303_recent03",
        status="rendered",
        created_at="2026-04-12T03:03:03Z",
        updated_at="2026-04-12T03:03:03Z",
        archive_path="uploads/tsk_20260412_030303_recent03.zip",
        workdir_path="workdir/tsk_20260412_030303_recent03",
        unified_json_path="workdir/tsk_20260412_030303_recent03/unified.json",
        report_payload_path="workdir/tsk_20260412_030303_recent03/report_payload.json",
        report_file_path="outputs/tsk_20260412_030303_recent03/report.docx",
    )

    response = client.post("/api/tasks/cleanup", json={"older_than_days": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"] == {
        "scanned_count": 3,
        "deleted_count": 1,
        "skipped_count": 2,
        "deleted_task_ids": ["tsk_20260410_010101_olddone01"],
    }

    assert _fetch_task_db_row(tmp_path, "tsk_20260410_010101_olddone01") is None
    assert not (tmp_path / "workdir" / "tsk_20260410_010101_olddone01").exists()

    assert _fetch_task_db_row(tmp_path, "tsk_20260410_020202_oldproc02") is not None
    assert (tmp_path / "workdir" / "tsk_20260410_020202_oldproc02").exists()

    assert _fetch_task_db_row(tmp_path, "tsk_20260412_030303_recent03") is not None
    assert (tmp_path / "outputs" / "tsk_20260412_030303_recent03").exists()


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
    task_row = _fetch_task_db_row(tmp_path, task_id)
    stored_zip_path = tmp_path / "uploads" / f"{task_id}.zip"
    unified_json_path = tmp_path / "workdir" / task_id / "unified.json"
    report_payload_path = tmp_path / "workdir" / task_id / "report_payload.json"
    extracted_log_path = tmp_path / "workdir" / task_id / "logs" / "system.log"
    extracted_info_path = tmp_path / "workdir" / task_id / "meta" / "info.txt"

    assert task_row is not None
    assert task_row["status"] == "completed"
    assert task_row["archive_path"] == f"uploads/{task_id}.zip"
    assert task_row["workdir_path"] == f"workdir/{task_id}"
    assert task_row["unified_json_path"] == f"workdir/{task_id}/unified.json"
    assert task_row["report_payload_path"] == f"workdir/{task_id}/report_payload.json"
    assert task_row["report_file_path"] is None
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


def test_create_task_marks_analyze_failed_when_analyzer_abstraction_errors(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    class FailingAnalyzer:
        def analyze(self, request):  # noqa: ANN001
            raise LogAnalyzerError(
                code="analyzer_timeout",
                message="Analyzer request timed out.",
                details={"analyzer_base_url": "http://127.0.0.1:8090"},
            )

    monkeypatch.setattr(task_service, "build_log_analyzer", lambda: FailingAnalyzer())

    response = client.post(
        "/api/tasks",
        files={"file": ("host-a-logs.zip", _build_zip_bytes({"logs/system.log": "system ok\n"}), "application/zip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 503
    payload = response.json()
    task_id = payload["error"]["details"]["task_id"]
    task_row = _fetch_task_db_row(tmp_path, task_id)

    assert payload == {
        "success": False,
        "error": {
            "code": "analyzer_timeout",
            "message": "Analyzer request timed out.",
            "details": {
                "analyzer_base_url": "http://127.0.0.1:8090",
                "task_id": task_id,
            },
        },
    }
    assert task_row is not None
    assert task_row["status"] == "analyze_failed"
    assert task_row["unified_json_path"] is None
    assert task_row["report_payload_path"] is None
    assert json.loads(task_row["error_details"]) == {
        "analyzer_base_url": "http://127.0.0.1:8090",
    }
    assert (tmp_path / "uploads" / f"{task_id}.zip").exists()
    assert (tmp_path / "workdir" / task_id / "logs" / "system.log").exists()


def test_create_task_returns_render_failed_when_optional_render_attempt_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REPORT_RENDERING_ENABLED", "true")

    monkeypatch.setattr(
        task_service,
        "maybe_render_report_from_payload_file",
        lambda task_id, report_payload_path: ReportRenderResult(
            attempted=True,
            success=False,
            error_code="carbone_unreachable",
            error_message="Failed to reach the Carbone runtime.",
            renderer="HttpCarboneAdapter",
        ),
    )

    response = client.post(
        "/api/tasks",
        files={"file": ("host-a-logs.zip", _build_zip_bytes({"logs/system.log": "system ok\n"}), "application/zip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 201
    payload = response.json()
    task_id = payload["data"]["task_id"]
    task_row = _fetch_task_db_row(tmp_path, task_id)

    assert payload["data"]["status"] == "render_failed"
    assert payload["data"]["report_file_path"] is None
    assert task_row is not None
    assert task_row["status"] == "render_failed"
    assert task_row["error_code"] == "carbone_unreachable"
    assert task_row["report_payload_path"] == f"workdir/{task_id}/report_payload.json"
    assert task_row["error_details"] is None


def test_create_task_remote_mode_happy_path_uses_remote_analyzer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANALYZER_MODE", "remote")
    monkeypatch.setenv("ANALYZER_BASE_URL", "http://127.0.0.1:8090")

    captured_request: dict[str, object] = {}

    def fake_send_request(self, request):  # noqa: ANN001
        nonlocal captured_request
        captured_request = request.model_dump(mode="json")
        return LocalLogAnalyzer().analyze(request)

    monkeypatch.setattr(RemoteLogAnalyzer, "_send_request", fake_send_request)

    response = client.post(
        "/api/tasks",
        files={
            "file": (
                "spec-v1.zip",
                _build_zip_bytes(
                    {
                        str(fixture_path.relative_to(SPEC_V1_FIXTURE_DIR)): fixture_path.read_text(encoding="utf-8")
                        for fixture_path in sorted(
                            path for path in SPEC_V1_FIXTURE_DIR.rglob("*") if path.is_file()
                        )
                    }
                ),
                "application/zip",
            )
        },
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 201
    payload = response.json()
    task_id = payload["data"]["task_id"]
    task_row = _fetch_task_db_row(tmp_path, task_id)
    unified_json = UnifiedJsonV1.model_validate_json(
        (tmp_path / "workdir" / task_id / "unified.json").read_text(encoding="utf-8")
    )

    assert captured_request["request_version"] == "analyze-request/v1"
    assert captured_request["source"]["type"] == "directory"
    assert captured_request["archive_name"] == "spec-v1.zip"
    assert payload["data"]["status"] == "completed"
    assert payload["data"]["summary"] == {
        "service_count": 4,
        "container_count": 2,
        "issue_count": 3,
    }
    assert unified_json.host_info.hostname == "host-a"
    assert task_row is not None
    assert task_row["status"] == "completed"


def test_create_task_remote_mode_marks_analyze_failed_when_analyzer_is_unreachable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANALYZER_MODE", "remote")
    monkeypatch.setenv("ANALYZER_BASE_URL", "http://127.0.0.1:8090")

    def fake_send_request(self, request):  # noqa: ANN001, ARG001
        raise LogAnalyzerError(
            code="analyzer_unavailable",
            message="Failed to reach the analyzer service.",
            details={"analyzer_base_url": "http://127.0.0.1:8090"},
        )

    monkeypatch.setattr(RemoteLogAnalyzer, "_send_request", fake_send_request)

    response = client.post(
        "/api/tasks",
        files={"file": ("host-a-logs.zip", _build_zip_bytes({"logs/system.log": "system ok\n"}), "application/zip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 503
    payload = response.json()
    task_id = payload["error"]["details"]["task_id"]
    task_row = _fetch_task_db_row(tmp_path, task_id)

    assert payload["error"]["code"] == "analyzer_unavailable"
    assert task_row is not None
    assert task_row["status"] == "analyze_failed"
    assert task_row["error_code"] == "analyzer_unavailable"
    assert json.loads(task_row["error_details"]) == {
        "analyzer_base_url": "http://127.0.0.1:8090",
    }


def test_create_task_remote_mode_preserves_structured_unsupported_source_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANALYZER_MODE", "remote")
    monkeypatch.setenv("ANALYZER_BASE_URL", "http://analyzer.local")

    def fake_send_request(self, request):  # noqa: ANN001, ARG001
        raise LogAnalyzerError(
            code="unsupported_source_type",
            message="Only directory source is supported in analyze-request/v1.",
            details={
                "source_type": "archive",
                "status_code": 400,
                "analyzer_base_url": "http://analyzer.local",
            },
        )

    monkeypatch.setattr(RemoteLogAnalyzer, "_send_request", fake_send_request)

    response = client.post(
        "/api/tasks",
        files={"file": ("bundle.zip", _build_zip_bytes({"file.txt": "ok\n"}), "application/zip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["code"] == "unsupported_source_type"
    assert payload["error"]["details"]["source_type"] == "archive"

    task_id = payload["error"]["details"]["task_id"]
    task_row = _fetch_task_db_row(tmp_path, task_id)
    assert task_row is not None
    assert task_row["status"] == "analyze_failed"
    assert task_row["error_code"] == "unsupported_source_type"
    assert task_row["error_message"] == "Only directory source is supported in analyze-request/v1."
    assert json.loads(task_row["error_details"]) == {
        "analyzer_base_url": "http://analyzer.local",
        "source_type": "archive",
        "status_code": 400,
    }


def test_create_task_remote_mode_preserves_structured_source_not_found_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANALYZER_MODE", "remote")
    monkeypatch.setenv("ANALYZER_BASE_URL", "http://analyzer.local")

    def fake_send_request(self, request):  # noqa: ANN001, ARG001
        raise LogAnalyzerError(
            code="source_not_found",
            message="Requested source directory does not exist.",
            details={
                "path": "/tmp/missing",
                "status_code": 404,
                "analyzer_base_url": "http://analyzer.local",
            },
        )

    monkeypatch.setattr(RemoteLogAnalyzer, "_send_request", fake_send_request)

    response = client.post(
        "/api/tasks",
        files={"file": ("bundle.zip", _build_zip_bytes({"file.txt": "ok\n"}), "application/zip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["code"] == "source_not_found"
    assert payload["error"]["details"]["path"] == "/tmp/missing"

    task_id = payload["error"]["details"]["task_id"]
    task_row = _fetch_task_db_row(tmp_path, task_id)
    assert task_row is not None
    assert task_row["error_code"] == "source_not_found"
    assert json.loads(task_row["error_details"]) == {
        "analyzer_base_url": "http://analyzer.local",
        "path": "/tmp/missing",
        "status_code": 404,
    }


def test_create_task_remote_mode_marks_analyze_failed_when_analyzer_response_is_invalid(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANALYZER_MODE", "remote")
    monkeypatch.setenv("ANALYZER_BASE_URL", "http://127.0.0.1:8090")

    def fake_send_request(self, request):  # noqa: ANN001, ARG001
        raise LogAnalyzerError(
            code="analyzer_invalid_response",
            message="Analyzer response did not match the expected contract.",
            details={"analyzer_base_url": "http://127.0.0.1:8090"},
        )

    monkeypatch.setattr(RemoteLogAnalyzer, "_send_request", fake_send_request)

    response = client.post(
        "/api/tasks",
        files={"file": ("host-a-logs.zip", _build_zip_bytes({"logs/system.log": "system ok\n"}), "application/zip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 503
    payload = response.json()
    task_id = payload["error"]["details"]["task_id"]
    task_row = _fetch_task_db_row(tmp_path, task_id)

    assert payload["error"]["code"] == "analyzer_invalid_response"
    assert task_row is not None
    assert task_row["status"] == "analyze_failed"
    assert task_row["error_code"] == "analyzer_invalid_response"


def test_create_task_remote_mode_falls_back_to_stable_error_for_non_json_analyzer_500(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANALYZER_MODE", "remote")
    monkeypatch.setenv("ANALYZER_BASE_URL", "http://analyzer.local")

    def fake_send_request(self, request):  # noqa: ANN001, ARG001
        raise LogAnalyzerError(
            code="analyzer_request_failed",
            message="Analyzer service returned a non-success response.",
            details={
                "analyzer_base_url": "http://analyzer.local",
                "status_code": 500,
                "content_type": "text/plain",
                "response_excerpt": "plain 500 body",
            },
        )

    monkeypatch.setattr(RemoteLogAnalyzer, "_send_request", fake_send_request)

    response = client.post(
        "/api/tasks",
        files={"file": ("bundle.zip", _build_zip_bytes({"file.txt": "ok\n"}), "application/zip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["code"] == "analyzer_request_failed"
    assert payload["error"]["details"]["status_code"] == 500
    assert payload["error"]["details"]["content_type"] == "text/plain"

    task_id = payload["error"]["details"]["task_id"]
    task_row = _fetch_task_db_row(tmp_path, task_id)
    assert task_row is not None
    assert task_row["error_code"] == "analyzer_request_failed"
    assert json.loads(task_row["error_details"]) == {
        "analyzer_base_url": "http://analyzer.local",
        "content_type": "text/plain",
        "response_excerpt": "plain 500 body",
        "status_code": 500,
    }


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
            "message": "Only .zip, .tar.gz, and .tgz files are accepted.",
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


def _build_tar_gz_bytes(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()

    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in entries.items():
            encoded = content.encode("utf-8")
            tar_info = tarfile.TarInfo(name=name)
            tar_info.size = len(encoded)
            archive.addfile(tar_info, io.BytesIO(encoded))

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


def _fetch_task_db_row(root_dir: Path, task_id: str) -> sqlite3.Row | None:
    db_path = root_dir / "tasks.sqlite3"
    if not db_path.exists():
        return None

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(
            """
            SELECT
                task_id,
                status,
                created_at,
                updated_at,
                archive_path,
                workdir_path,
                unified_json_path,
                report_payload_path,
                report_file_path,
                error_code,
                error_message,
                error_details
            FROM tasks
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
    finally:
        connection.close()


def _write_task_db_row(
    root_dir: Path,
    *,
    task_id: str,
    status: str,
    created_at: str,
    updated_at: str,
    archive_path: str | None,
    workdir_path: str | None,
    unified_json_path: str | None,
    report_payload_path: str | None,
    report_file_path: str | None,
    error_code: str | None = None,
    error_message: str | None = None,
    error_details: str | None = None,
) -> None:
    db_path = root_dir / "tasks.sqlite3"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archive_path TEXT,
                workdir_path TEXT,
                unified_json_path TEXT,
                report_payload_path TEXT,
                report_file_path TEXT,
                error_code TEXT,
                error_message TEXT,
                error_details TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO tasks (
                task_id,
                status,
                created_at,
                updated_at,
                archive_path,
                workdir_path,
                unified_json_path,
                report_payload_path,
                report_file_path,
                error_code,
                error_message,
                error_details
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                status,
                created_at,
                updated_at,
                archive_path,
                workdir_path,
                unified_json_path,
                report_payload_path,
                report_file_path,
                error_code,
                error_message,
                error_details,
            ),
        )
        connection.commit()
    finally:
        connection.close()
