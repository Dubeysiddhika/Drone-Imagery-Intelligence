from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from ..config import DATABASE_URL


def create_database_engine(database_url: str = DATABASE_URL):
    """Create a SQLAlchemy engine with dialect-appropriate connection options."""
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        return sqlalchemy_create_engine(
            url,
            connect_args={"check_same_thread": False},
        )
    if url.get_backend_name() == "postgresql" and url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return sqlalchemy_create_engine(url, pool_pre_ping=True)


engine = create_database_engine()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()


def ensure_detection_columns(bind=engine) -> None:
    """Add detection fields missing from databases created by older versions."""
    columns = {
        column["name"]
        for column in inspect(bind).get_columns("detections")
    }

    with bind.begin() as connection:
        if "class_id" not in columns:
            connection.execute(
                text("ALTER TABLE detections ADD COLUMN class_id INTEGER")
            )
        if "created_at" not in columns and bind.dialect.name == "postgresql":
            connection.execute(
                text(
                    "ALTER TABLE detections "
                    "ADD COLUMN created_at TIMESTAMP WITHOUT TIME ZONE"
                )
            )
        elif "created_at" not in columns:
            connection.execute(
                text("ALTER TABLE detections ADD COLUMN created_at DATETIME")
            )


def ensure_image_location_column(bind=engine) -> None:
    """Add the appropriate nullable location column to an existing schema."""
    columns = {
        column["name"]
        for column in inspect(bind).get_columns("images")
    }
    if bind.dialect.name == "postgresql":
        with bind.begin() as connection:
            if "location" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE images "
                        "ADD COLUMN location geometry(POINT, 4326)"
                    )
                )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_images_location "
                    "ON images USING GIST (location)"
                )
            )
    elif "location" not in columns:
        with bind.begin() as connection:
            connection.execute(
                text("ALTER TABLE images ADD COLUMN location TEXT")
            )


def verify_postgis(bind=engine) -> str:
    """Verify the configured PostgreSQL database has PostGIS enabled."""
    if bind.dialect.name != "postgresql":
        raise ValueError("PostGIS verification requires a PostgreSQL engine")

    try:
        with bind.connect() as connection:
            return str(connection.execute(text("SELECT PostGIS_Full_Version()")).scalar_one())
    except Exception as error:
        raise RuntimeError(
            "Could not verify PostGIS on DATABASE_URL. Ensure PostgreSQL is "
            "running, the database exists, and an administrator has run "
            "CREATE EXTENSION IF NOT EXISTS postgis;"
        ) from error


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()