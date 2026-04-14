from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from app.parsers.linux_default_parser import LinuxDefaultParser
from app.schemas.unified_json import UnifiedJsonParser, UnifiedJsonV1


XRAY_ROOT_MARKERS = ("system-logs", "resource-snapshots", "xray-logs")


@dataclass(frozen=True)
class XrayCollectorInput:
    root: Path
    hostnamectl_path: Path | None
    timedatectl_path: Path | None
    uname_path: Path | None
    uptime_path: Path | None
    list_boot_path: Path | None
    minion_service_status_path: Path | None
    systemctl_failed_path: Path | None
    docker_ps_path: Path | None
    ip_addr_path: Path | None


class XrayCollectorParser:
    parser_name = "xray-collector-parser"
    parser_version = "0.1.0"

    def detect(self, analysis_root: Path) -> XrayCollectorInput | None:
        candidates = [analysis_root.resolve()]
        candidates.extend(
            path.resolve()
            for path in sorted(analysis_root.iterdir())
            if path.is_dir()
        )

        for candidate in candidates:
            detected = self._detect_root(candidate)
            if detected is not None:
                return detected

        return None

    def parse(
        self,
        *,
        task_id: str,
        analysis_root: Path,
        archive_name: str | None = None,
        archive_size_bytes: int | None = None,
    ) -> UnifiedJsonV1:
        detected = self.detect(analysis_root)
        if detected is None:
            raise ValueError("xray collector input was not detected")

        with TemporaryDirectory(prefix="xray-canonical-") as temp_dir:
            canonical_root = Path(temp_dir)
            self._materialize_canonical_bundle(detected, canonical_root)
            unified_json = LinuxDefaultParser().parse(
                task_id=task_id,
                analysis_root=canonical_root,
                archive_name=archive_name,
                archive_size_bytes=archive_size_bytes,
            )

        unified_json.parser = UnifiedJsonParser(
            name=self.parser_name,
            version=self.parser_version,
        )
        unified_json.warnings = [
            "xray-collector v1 input detected and normalized into canonical parser inputs.",
            *unified_json.warnings,
        ]
        unified_json.metadata = {
            **unified_json.metadata,
            "collector_type": "xray-collector/v1",
            "xray_root_path": detected.root.as_posix(),
            "xray_adapted_system_info": self._has_host_data(detected),
            "xray_adapted_service_inventory": detected.minion_service_status_path is not None,
            "xray_adapted_systemctl_failed": detected.systemctl_failed_path is not None,
            "xray_adapted_docker_ps": detected.docker_ps_path is not None,
        }
        return unified_json

    def _detect_root(self, candidate: Path) -> XrayCollectorInput | None:
        if not candidate.is_dir():
            return None

        if not any((candidate / marker).exists() for marker in XRAY_ROOT_MARKERS):
            return None

        system_logs_dir = candidate / "system-logs"
        resource_dir = candidate / "resource-snapshots"
        xray_logs_dir = candidate / "xray-logs" / "container-logs"
        network_dir = candidate / "network"

        detected = XrayCollectorInput(
            root=candidate,
            hostnamectl_path=_first_existing(
                system_logs_dir / "hostnamectl.txt",
            ),
            timedatectl_path=_first_existing(
                system_logs_dir / "timedatectl.txt",
            ),
            uname_path=_first_existing(
                system_logs_dir / "uname.txt",
            ),
            uptime_path=_first_existing(
                system_logs_dir / "uptime.txt",
            ),
            list_boot_path=_first_existing(
                system_logs_dir / "list-boot.txt",
            ),
            minion_service_status_path=_first_existing(
                candidate / "minion-logs" / "minion-service-status.txt",
            ),
            systemctl_failed_path=_first_existing(
                system_logs_dir / "systemctl-failed.txt",
            ),
            docker_ps_path=_first_existing(
                resource_dir / "docker-ps-a.txt",
                xray_logs_dir / "docker_ps.log",
            ),
            ip_addr_path=_first_existing(
                network_dir / "ip-addr.txt",
                system_logs_dir / "ip.addr.txt",
            ),
        )

        if not any(
            [
                self._has_host_data(detected),
                detected.minion_service_status_path is not None,
                detected.systemctl_failed_path is not None,
                detected.docker_ps_path is not None,
            ]
        ):
            return None

        return detected

    def _materialize_canonical_bundle(
        self,
        detected: XrayCollectorInput,
        canonical_root: Path,
    ) -> None:
        system_dir = canonical_root / "system"
        containers_dir = canonical_root / "containers"
        system_dir.mkdir(parents=True, exist_ok=True)
        containers_dir.mkdir(parents=True, exist_ok=True)

        system_info_lines = self._build_system_info_lines(detected)
        if system_info_lines:
            (system_dir / "system_info").write_text(
                "\n".join(system_info_lines) + "\n",
                encoding="utf-8",
            )

        systemctl_status_lines = self._build_systemctl_status_lines(detected)
        if systemctl_status_lines:
            (system_dir / "systemctl_status").write_text(
                "\n".join(systemctl_status_lines) + "\n",
                encoding="utf-8",
            )

        docker_ps_content = self._build_docker_ps_content(detected)
        if docker_ps_content:
            (containers_dir / "docker_ps").write_text(
                docker_ps_content + "\n",
                encoding="utf-8",
            )

    def _build_system_info_lines(self, detected: XrayCollectorInput) -> list[str]:
        values: dict[str, str] = {}

        if detected.hostnamectl_path is not None:
            hostnamectl_text = detected.hostnamectl_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
            hostname = _extract_field(hostnamectl_text, r"Static hostname:\s*(.+)")
            pretty_name = _extract_field(
                hostnamectl_text,
                r"Operating System:\s*(.+)",
            )
            kernel = _extract_field(hostnamectl_text, r"Kernel:\s*Linux\s+(.+)")
            if hostname:
                values["hostname"] = hostname
            if pretty_name:
                values["pretty_name"] = pretty_name
            if kernel:
                values["kernel"] = kernel

        if detected.uname_path is not None:
            uname_line = _first_non_comment_line(
                detected.uname_path.read_text(encoding="utf-8", errors="ignore"),
            )
            if uname_line:
                parts = uname_line.split()
                if len(parts) >= 3:
                    values.setdefault("hostname", parts[1])
                    values.setdefault("kernel", parts[2])

        if detected.timedatectl_path is not None:
            timedatectl_text = detected.timedatectl_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
            timezone = _extract_field(timedatectl_text, r"Time zone:\s*([A-Za-z0-9_./+-]+)")
            if timezone:
                values["timezone"] = timezone

        if detected.uptime_path is not None:
            uptime_line = _first_non_comment_line(
                detected.uptime_path.read_text(encoding="utf-8", errors="ignore"),
            )
            uptime_seconds = _parse_uptime_shell_line(uptime_line) if uptime_line else None
            if uptime_seconds is not None:
                values["uptime_seconds"] = str(uptime_seconds)

        if detected.list_boot_path is not None:
            list_boot_text = detected.list_boot_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
            last_boot_at = _extract_last_boot_at(list_boot_text)
            if last_boot_at:
                values["last_boot_at"] = last_boot_at

        if detected.ip_addr_path is not None:
            ip_text = detected.ip_addr_path.read_text(encoding="utf-8", errors="ignore")
            ip_value = _extract_first_ipv4(ip_text)
            if ip_value:
                values["ip"] = ip_value

        ordered_keys = [
            "hostname",
            "ip",
            "pretty_name",
            "kernel",
            "timezone",
            "uptime_seconds",
            "last_boot_at",
        ]
        return [f"{key}={values[key]}" for key in ordered_keys if key in values]

    def _build_systemctl_status_lines(
        self,
        detected: XrayCollectorInput,
    ) -> list[str]:
        service_rows: dict[str, str] = {}

        inventory_row = self._build_minion_inventory_row(detected)
        if inventory_row is not None:
            service_rows[inventory_row.split()[0]] = inventory_row

        if detected.systemctl_failed_path is not None:
            for raw_line in detected.systemctl_failed_path.read_text(
                encoding="utf-8",
                errors="ignore",
            ).splitlines():
                line = raw_line.strip().lstrip("●").strip()
                if not line or line.startswith("#"):
                    continue
                match = re.match(
                    r"^([A-Za-z0-9_.:@-]+\.service)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+(.*\S))?$",
                    line,
                )
                if not match:
                    continue
                description = match.group(5) or ""
                service_rows[match.group(1)] = " ".join(
                    [
                        match.group(1),
                        match.group(2),
                        match.group(3),
                        match.group(4),
                        description,
                    ]
                ).strip()

        if not service_rows:
            return []

        lines = ["UNIT LOAD ACTIVE SUB DESCRIPTION"]
        lines.extend(service_rows[unit_name] for unit_name in sorted(service_rows))
        return lines

    def _build_minion_inventory_row(
        self,
        detected: XrayCollectorInput,
    ) -> str | None:
        if detected.minion_service_status_path is None:
            return None

        unit_line = None
        loaded_line = None
        active_line = None

        for raw_line in detected.minion_service_status_path.read_text(
            encoding="utf-8",
            errors="ignore",
        ).splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if unit_line is None and ".service -" in line:
                unit_line = line.lstrip("●").strip()
                continue
            if loaded_line is None and line.startswith("Loaded:"):
                loaded_line = line
                continue
            if active_line is None and line.startswith("Active:"):
                active_line = line
                continue

        if unit_line is None or loaded_line is None or active_line is None:
            return None

        unit_match = re.match(r"^([A-Za-z0-9_.:@-]+\.service)\s+-\s+(.+)$", unit_line)
        loaded_match = re.match(r"^Loaded:\s+(\S+)\s+.*$", loaded_line)
        active_match = re.match(r"^Active:\s+(\S+)\s+\(([^)]+)\).*$", active_line)
        if not unit_match or not loaded_match or not active_match:
            return None

        description = unit_match.group(2)
        enabled = _extract_enabled_value(loaded_line)
        if enabled is not None:
            description = f"{description} [enabled={'true' if enabled else 'false'}]"

        return " ".join(
            [
                unit_match.group(1),
                loaded_match.group(1),
                active_match.group(1),
                active_match.group(2),
                description,
            ]
        ).strip()

    def _build_docker_ps_content(self, detected: XrayCollectorInput) -> str | None:
        if detected.docker_ps_path is None:
            return None

        kept_lines: list[str] = []
        started = False
        for raw_line in detected.docker_ps_path.read_text(
            encoding="utf-8",
            errors="ignore",
        ).splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                if started:
                    kept_lines.append("")
                continue
            if stripped.startswith("#"):
                continue
            if not started:
                if "IMAGE" in stripped and "STATUS" in stripped and "NAMES" in stripped:
                    started = True
                    kept_lines.append(stripped)
                continue
            kept_lines.append(line)

        normalized_lines = [line for line in kept_lines if line.strip()]
        if not normalized_lines:
            return None
        return "\n".join(normalized_lines)

    def _has_host_data(self, detected: XrayCollectorInput) -> bool:
        return any(
            [
                detected.hostnamectl_path is not None,
                detected.timedatectl_path is not None,
                detected.uname_path is not None,
                detected.uptime_path is not None,
                detected.ip_addr_path is not None,
            ]
        )


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def _extract_field(content: str, pattern: str) -> str | None:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.search(pattern, line)
        if match:
            return match.group(1).strip()
    return None


def _first_non_comment_line(content: str) -> str | None:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            return line
    return None


def _parse_uptime_shell_line(line: str) -> int | None:
    normalized = " ".join(line.split())

    day_time_match = re.search(r"up (\d+) days?, (\d+):(\d+)", normalized)
    if day_time_match:
        days = int(day_time_match.group(1))
        hours = int(day_time_match.group(2))
        minutes = int(day_time_match.group(3))
        return days * 86400 + hours * 3600 + minutes * 60

    day_minute_match = re.search(r"up (\d+) days?, (\d+) min", normalized)
    if day_minute_match:
        days = int(day_minute_match.group(1))
        minutes = int(day_minute_match.group(2))
        return days * 86400 + minutes * 60

    time_match = re.search(r"up (\d+):(\d+)", normalized)
    if time_match:
        hours = int(time_match.group(1))
        minutes = int(time_match.group(2))
        return hours * 3600 + minutes * 60

    minute_match = re.search(r"up (\d+) min", normalized)
    if minute_match:
        return int(minute_match.group(1)) * 60

    return None


def _extract_first_ipv4(content: str) -> str | None:
    for match in re.finditer(r"\binet\s+(\d+\.\d+\.\d+\.\d+)(?:/\d+)?\b", content):
        ip_value = match.group(1)
        if not ip_value.startswith("127."):
            return ip_value
    return None


def _extract_last_boot_at(content: str) -> str | None:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = re.match(
            r"^0\s+\S+\s+\w{3}\s+(\d{4}-\d{2}-\d{2})\s+"
            r"(\d{2}:\d{2}:\d{2})\s+(UTC)(?:—|--|-).*$",
            line,
        )
        if not match:
            continue

        date_part = match.group(1)
        time_part = match.group(2)
        timezone = match.group(3)
        if timezone != "UTC":
            return None
        return f"{date_part}T{time_part}Z"

    return None


def _extract_enabled_value(loaded_line: str) -> bool | None:
    match = re.search(r";\s*(enabled|disabled)\s*;", loaded_line)
    if not match:
        return None
    return match.group(1) == "enabled"
