from contextlib import contextmanager
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash

from .domain import (
    DEVICE_PROFILES,
    POWER_POINT_PROFILES,
    build_device_topic,
    build_power_topic,
)


def database_is_configured(app):
    keys = [
        "POSTGRES_HOST",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]
    return all(str(app.config.get(key, "")).strip() for key in keys)


@contextmanager
def get_connection(app):
    connection = psycopg2.connect(
        host=app.config["POSTGRES_HOST"],
        port=app.config["POSTGRES_PORT"],
        dbname=app.config["POSTGRES_DB"],
        user=app.config["POSTGRES_USER"],
        password=app.config["POSTGRES_PASSWORD"],
    )
    try:
        yield connection
    finally:
        connection.close()


def bootstrap_database(app):
    schema_path = Path(app.config["SCHEMA_PATH"])
    schema_sql = schema_path.read_text(encoding="utf-8")

    with get_connection(app) as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)
            _seed_devices(cursor)
            _seed_monitoring_points(cursor)
            _seed_admin_user(app, cursor)
        connection.commit()


def _seed_admin_user(app, cursor):
    cursor.execute(
        """
        INSERT INTO usuarios (nombre, email, password, rol, activo)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (email) DO NOTHING
        """,
        (
            app.config["DEFAULT_ADMIN_NAME"],
            app.config["DEFAULT_ADMIN_EMAIL"],
            generate_password_hash(app.config["DEFAULT_ADMIN_PASSWORD"]),
            "admin",
            True,
        ),
    )


def _seed_devices(cursor):
    for profile in DEVICE_PROFILES:
        cursor.execute(
            """
            INSERT INTO dispositivos (ciudad, planta, nombre, topic_mqtt, activo)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (topic_mqtt) DO NOTHING
            """,
            (
                profile["ciudad"],
                profile["planta"],
                profile["nombre"],
                build_device_topic(profile),
                True,
            ),
        )


def _seed_monitoring_points(cursor):
    for point in POWER_POINT_PROFILES:
        cursor.execute(
            """
            INSERT INTO puntos_monitoreo (
                zona, subestacion, circuito, elemento, tipo, voltaje_nominal_kv, topic_mqtt, activo
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (elemento) DO UPDATE SET
                zona = EXCLUDED.zona,
                subestacion = EXCLUDED.subestacion,
                circuito = EXCLUDED.circuito,
                tipo = EXCLUDED.tipo,
                voltaje_nominal_kv = EXCLUDED.voltaje_nominal_kv,
                topic_mqtt = EXCLUDED.topic_mqtt
            """,
            (
                point["zona"],
                point["subestacion"],
                point["circuito"],
                point["elemento"],
                point["tipo"],
                point["voltaje_nominal_kv"],
                build_power_topic(point),
                True,
            ),
        )


def fetch_all(app, query, params=None):
    with get_connection(app) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params or ())
            return [dict(row) for row in cursor.fetchall()]


def fetch_one(app, query, params=None):
    with get_connection(app) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params or ())
            row = cursor.fetchone()
            return dict(row) if row else None
