import os
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


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


DATABASE_URL = get_database_url()