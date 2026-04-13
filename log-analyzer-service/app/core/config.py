import os
from dataclasses import dataclass


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_host: str
    app_port: int
    analyzer_version: str
    analyze_timeout_seconds: float
    allow_directory_source: bool


def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("ANALYZER_APP_NAME", "log-analyzer-service"),
        app_host=os.getenv("ANALYZER_APP_HOST", "0.0.0.0"),
        app_port=int(os.getenv("ANALYZER_APP_PORT", "8090")),
        analyzer_version=os.getenv("ANALYZER_VERSION", "0.1.0"),
        analyze_timeout_seconds=float(os.getenv("ANALYZE_TIMEOUT_SECONDS", "30")),
        allow_directory_source=_get_bool_env("ALLOW_DIRECTORY_SOURCE", True),
    )
