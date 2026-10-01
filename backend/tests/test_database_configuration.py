import os
import unittest
import uuid
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from app.config import PROJECT_ROOT, get_database_url
from app.models.database import (
    Base,
    create_database_engine,
    ensure_image_location_column,
    verify_postgis,
)
from app.models.models import Detection, DroneImage


class DatabaseConfigurationTests(unittest.TestCase):
    def test_development_fallback_is_absolute_and_project_root_relative(self):
        url = get_database_url({"APP_ENV": "development"})

        self.assertEqual(
            url,
            f"sqlite:///{(PROJECT_ROOT / 'drone.db').as_posix()}",
        )
        self.assertTrue(Path(PROJECT_ROOT / "drone.db").is_absolute())

    def test_production_requires_database_url(self):
        with self.assertRaisesRegex(RuntimeError, "DATABASE_URL must be set"):
            get_database_url({"APP_ENV": "production"})

    def test_postgresql_url_uses_psycopg_driver_without_connecting(self):
        url = "postgresql://postgres:placeholder@localhost/drone_intelligence"
        self.assertEqual(get_database_url({"DATABASE_URL": url}), url)

        engine = create_database_engine(url)
        try:
            self.assertEqual(engine.dialect.name, "postgresql")
            self.assertEqual(engine.dialect.driver, "psycopg")
            self.assertEqual(engine.url.drivername, "postgresql+psycopg")
        finally:
            engine.dispose()

    def test_image_ddl_uses_postgis_point_type(self):
        ddl = str(
            CreateTable(DroneImage.__table__).compile(
                dialect=postgresql.dialect()
            )
        )

        self.assertIn("location geometry(POINT,4326)", ddl)

    def test_sqlite_image_location_and_detection_relationship(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        try:
            with Session() as session:
                no_gps_image = DroneImage(
                    filename="no-gps.jpg",
                    filepath="no-gps.jpg",
                )
                located_image = DroneImage(
                    filename="located.jpg",
                    filepath="located.jpg",
                    latitude=-33.86,
                    longitude=151.21,
                    altitude=None,
                )
                session.add_all([no_gps_image, located_image])
                session.flush()
                session.add(
                    Detection(
                        image_id=located_image.id,
                        class_id=1,
                        class_name="vehicle",
                        confidence=0.9,
                        x1=1,
                        y1=2,
                        x2=3,
                        y2=4,
                    )
                )
                session.commit()

                session.refresh(no_gps_image)
                session.refresh(located_image)
                self.assertIsNone(no_gps_image.location)
                self.assertEqual(
                    located_image.location,
                    "SRID=4326;POINT(151.21 -33.86)",
                )
                self.assertEqual(len(located_image.detections), 1)
                self.assertFalse(hasattr(located_image.detections[0], "latitude"))
                self.assertFalse(hasattr(located_image.detections[0], "longitude"))
        finally:
            engine.dispose()

    def test_existing_sqlite_images_table_gets_additive_location_column(self):
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE images "
                        "(id INTEGER PRIMARY KEY, filename TEXT NOT NULL)"
                    )
                )

            ensure_image_location_column(engine)

            columns = {
                column["name"]
                for column in inspect(engine).get_columns("images")
            }
            self.assertIn("location", columns)
        finally:
            engine.dispose()


@unittest.skipUnless(
    os.environ.get("TEST_POSTGIS_DATABASE_URL"),
    "Set TEST_POSTGIS_DATABASE_URL to a dedicated PostGIS test database",
)
class PostGISIntegrationTests(unittest.TestCase):
    def test_point_storage_srid_and_image_detection_link(self):
        database_url = os.environ["TEST_POSTGIS_DATABASE_URL"]
        admin_engine = create_database_engine(database_url)
        schema = f"phase5_test_{uuid.uuid4().hex}"
        test_engine = None

        try:
            verify_postgis(admin_engine)
            with admin_engine.begin() as connection:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))

            test_engine = create_engine(
                database_url,
                connect_args={"options": f"-csearch_path={schema},public"},
                pool_pre_ping=True,
            )
            Base.metadata.create_all(test_engine)
            Session = sessionmaker(bind=test_engine)
            with Session() as session:
                no_gps_image = DroneImage(
                    filename="no-gps.jpg",
                    filepath="no-gps.jpg",
                )
                located_image = DroneImage(
                    filename="located.jpg",
                    filepath="located.jpg",
                    latitude=-33.86,
                    longitude=151.21,
                )
                session.add_all([no_gps_image, located_image])
                session.flush()
                session.add(
                    Detection(
                        image_id=located_image.id,
                        class_id=1,
                        class_name="vehicle",
                        confidence=0.9,
                        x1=1,
                        y1=2,
                        x2=3,
                        y2=4,
                    )
                )
                session.commit()
                geometry, srid = session.execute(
                    text(
                        "SELECT ST_AsText(location), ST_SRID(location) "
                        "FROM images WHERE id = :image_id"
                    ),
                    {"image_id": located_image.id},
                ).one()
                null_geometry = session.execute(
                    text("SELECT location IS NULL FROM images WHERE id = :image_id"),
                    {"image_id": no_gps_image.id},
                ).scalar_one()

                self.assertEqual(geometry, "POINT(151.21 -33.86)")
                self.assertEqual(srid, 4326)
                self.assertTrue(null_geometry)
                self.assertEqual(len(located_image.detections), 1)
                self.assertFalse(hasattr(located_image.detections[0], "latitude"))
        finally:
            if test_engine is not None:
                test_engine.dispose()
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            admin_engine.dispose()


if __name__ == "__main__":
    unittest.main()