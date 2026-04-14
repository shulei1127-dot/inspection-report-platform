import shutil
from pathlib import Path

from app.services.product_router import ProductRouter


XRAY_FIXTURE_DIR = (
    Path(__file__).parent / "fixtures" / "xray_collector_v1" / "sample-bundle"
)


def test_product_router_routes_xray_input_to_xray_parser(tmp_path: Path) -> None:
    xray_root = tmp_path / "xray-collector.20260413123039"
    shutil.copytree(XRAY_FIXTURE_DIR, xray_root)

    routed = ProductRouter().route(tmp_path)

    assert routed.product_type == "xray"
    assert routed.parser_id == "xray-collector-parser"


def test_product_router_routes_canonical_input_to_unknown_linux_parser(tmp_path: Path) -> None:
    system_dir = tmp_path / "system"
    container_dir = tmp_path / "containers"
    system_dir.mkdir(parents=True)
    container_dir.mkdir(parents=True)

    (system_dir / "system_info").write_text(
        "\n".join(
            [
                "hostname=host-router",
                "kernel=5.15.0-test",
                "timezone=UTC",
                "uptime_seconds=1200",
                "last_boot_at=2026-04-13T08:00:00Z",
            ]
        ),
        encoding="utf-8",
    )
    (system_dir / "systemctl_status").write_text(
        "UNIT LOAD ACTIVE SUB DESCRIPTION\n"
        "nginx.service loaded active running nginx service\n",
        encoding="utf-8",
    )
    (container_dir / "docker_ps").write_text(
        "NAMES\tIMAGE\tSTATUS\tPORTS\n"
        "api\tnginx:1.27\tUp 5 minutes\t0.0.0.0:8080->80/tcp\n",
        encoding="utf-8",
    )

    routed = ProductRouter().route(tmp_path)

    assert routed.product_type == "unknown"
    assert routed.parser_id == "linux-default-parser"
