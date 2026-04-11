import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.report_payload import ReportPayloadV1
from app.schemas.unified_json import UnifiedJsonV1


client = TestClient(app)


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
        "issue_count": 0,
    }

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
    assert unified_json.summary.overall_status == "unknown"
    assert unified_json.summary.service_count == 0
    assert unified_json.summary.container_count == 0
    assert unified_json.summary.issue_count == 0
    assert unified_json.services == []
    assert unified_json.containers == []
    assert unified_json.issues == []
    assert unified_json.parser is not None
    assert unified_json.parser.name == "upload-parser-stub"
    assert unified_json.source is not None
    assert unified_json.source.archive_name == "host-a-logs.zip"
    assert unified_json.metadata["extracted_file_count"] == 2

    report_payload_data = json.loads(report_payload_path.read_text(encoding="utf-8"))
    report_payload = ReportPayloadV1.model_validate(report_payload_data)

    assert report_payload.payload_version == "report-payload/v1"
    assert report_payload.report.task_id == task_id
    assert report_payload.report.report_lang == "zh-CN"
    assert report_payload.host.hostname == "host-a-logs"
    assert report_payload.summary.overall_status == "unknown"
    assert report_payload.summary.overall_status_label == "Unknown"
    assert report_payload.service_rows == []
    assert report_payload.container_rows == []
    assert report_payload.issue_rows == []
    assert report_payload.highlights == [
        f"Upload task {task_id} completed and unified JSON was generated.",
    ]
    assert report_payload.recommendations == [
        "Review results produced by upload-parser-stub and replace stub parsing with real inspection logic.",
    ]
    assert report_payload.appendix["parser_name"] == "upload-parser-stub"
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
