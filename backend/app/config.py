import os
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def resolve_project_path(
    configured_path: str | Path | None,
    default_path: str | Path,
) -> Path:
    """Resolve configured paths consistently from the repository root."""
    raw_path = configured_path if configured_path not in (None, "") else default_path
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def get_database_url(environment: Mapping[str, str] | None = None) -> str:
    """Resolve the configured database URL or the development SQLite fallback."""
    values = os.environ if environment is None else environment
    configured_url = values.get("DATABASE_URL", "").strip()
    if configured_url:
        url = make_url(configured_url)
        if url.get_backend_name() == "sqlite" and url.database:
            database_path = url.database
            if database_path == ":memory:" or database_path.startswith("file:"):
                return configured_url
            path = Path(database_path).expanduser()
            if not path.is_absolute():
                path = (PROJECT_ROOT / path).resolve()
                return url.set(database=path.as_posix()).render_as_string(
                    hide_password=False
                )
        return configured_url

    app_environment = values.get("APP_ENV", "development").strip().lower()
    if app_environment in {"production", "prod"}:
        raise RuntimeError(
            "DATABASE_URL must be set when APP_ENV is production. "
            "Configure a PostgreSQL URL using the postgresql+psycopg scheme."
        )

    return f"sqlite:///{(PROJECT_ROOT / 'drone.db').as_posix()}"


def get_cors_origins(environment: Mapping[str, str] | None = None) -> list[str]:
    """Return explicit browser origins; credentials must never use wildcard CORS."""
    values = os.environ if environment is None else environment
    configured = values.get("CORS_ORIGINS", "").strip()
    if configured:
        origins = [item.strip().rstrip("/") for item in configured.split(",") if item.strip()]
        if "*" in origins:
            raise RuntimeError("CORS_ORIGINS cannot contain '*' when credentialed sessions are enabled.")
        return list(dict.fromkeys(origins))

    defaults = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ]
    frontend_base = values.get("FRONTEND_BASE_URL", "").strip()
    if frontend_base:
        parsed = urlsplit(frontend_base)
        if parsed.scheme and parsed.netloc:
            defaults.insert(0, f"{parsed.scheme}://{parsed.netloc}")
    return list(dict.fromkeys(defaults))


DATABASE_URL = get_database_url()
