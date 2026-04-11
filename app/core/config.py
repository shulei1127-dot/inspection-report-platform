import os
from dataclasses import dataclass
from pathlib import Path


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_host: str
    app_port: int
    uploads_dir: Path
    workdir_dir: Path
    outputs_dir: Path
    templates_dir: Path
    default_report_template_path: Path
    report_rendering_enabled: bool


def get_settings() -> Settings:
    templates_dir = Path(os.getenv("TEMPLATES_DIR", "templates"))

    return Settings(
        app_name=os.getenv("APP_NAME", "inspection-report-platform"),
        app_env=os.getenv("APP_ENV", "dev"),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=int(os.getenv("APP_PORT", "8000")),
        uploads_dir=Path(os.getenv("UPLOADS_DIR", "uploads")),
        workdir_dir=Path(os.getenv("WORKDIR_DIR", "workdir")),
        outputs_dir=Path(os.getenv("OUTPUTS_DIR", "outputs")),
        templates_dir=templates_dir,
        default_report_template_path=Path(
            os.getenv(
                "DEFAULT_REPORT_TEMPLATE_PATH",
                (templates_dir / "inspection_report.docx").as_posix(),
            )
        ),
        report_rendering_enabled=_get_bool_env("REPORT_RENDERING_ENABLED", False),
    )
