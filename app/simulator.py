import logging
import random
import threading
import time

from psycopg2.extras import Json, RealDictCursor

from .db import get_connection
from .domain import (
    POWER_POINT_PROFILE_MAP,
    build_power_topic,
    evaluate_power_quality,
    generate_power_quality_reading,
    humanize_name,
)


class IoTSimulator:
    def __init__(self, app):
        self.app = app
        self.interval = app.config["SIMULATION_INTERVAL"]
        self._thread = None
        self._stop_event = threading.Event()
        self.logger = logging.getLogger(__name__)

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(
            target=self._loop,
            name="electiva-simulator",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _loop(self):
        while not self._stop_event.is_set():
            try:
                self.run_cycle()
            except Exception as exc:  # pragma: no cover
                self.logger.exception("No fue posible ejecutar el simulador: %s", exc)
            time.sleep(self.interval)

    def run_cycle(self):
        with self.app.app_context():
            with get_connection(self.app) as connection:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    point_energy = self._load_latest_point_energy(cursor)

                    cursor.execute(
                        """
                        SELECT
                            id,
                            zona,
                            subestacion,
                            circuito,
                            elemento,
                            tipo,
                            voltaje_nominal_kv,
                            topic_mqtt,
                            activo
                        FROM puntos_monitoreo
                        ORDER BY id
                        """
                    )
                    for point in cursor.fetchall():
                        if not point["activo"]:
                            continue
                        self._store_power_quality(cursor, point, point_energy)

                connection.commit()

    def _store_power_quality(self, cursor, point, point_energy):
        profile = POWER_POINT_PROFILE_MAP.get(point["elemento"])
        if not profile:
            return

        energy_base = point_energy.get(point["id"], round(random.uniform(50.0, 300.0), 4))
        reading = generate_power_quality_reading(profile, energy_base, self.interval)
        status, alerts = evaluate_power_quality(reading, profile)

        cursor.execute(
            """
            INSERT INTO mediciones_calidad_energia (
                punto_id,
                topic,
                timestamp_medicion,
                voltaje_kv,
                corriente_a,
                frecuencia_hz,
                factor_potencia,
                thd_v_pct,
                thd_i_pct,
                potencia_activa_kw,
                potencia_reactiva_kvar,
                potencia_aparente_kva,
                energia_kwh,
                carga_pct,
                estado_calidad
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                point["id"],
                point["topic_mqtt"] or build_power_topic(profile),
                reading["timestamp"],
                reading["voltaje_kv"],
                reading["corriente_a"],
                reading["frecuencia_hz"],
                reading["factor_potencia"],
                reading["thd_v_pct"],
                reading["thd_i_pct"],
                reading["potencia_activa_kw"],
                reading["potencia_reactiva_kvar"],
                reading["potencia_aparente_kva"],
                reading["energia_kwh"],
                reading["carga_pct"],
                status,
            ),
        )
        measurement_id = cursor.fetchone()["id"]

        for alert_type, detail in alerts:
            cursor.execute(
                """
                INSERT INTO alertas_calidad_energia (
                    medicion_id,
                    tipo_alerta,
                    detalle,
                    estado_alerta,
                    updated_at
                ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                RETURNING id
                """,
                (measurement_id, alert_type, detail, "nueva"),
            )
            alert_id = cursor.fetchone()["id"]

            cursor.execute(
                """
                INSERT INTO alertas_seguimiento (
                    alerta_id,
                    accion,
                    estado_nuevo,
                    comentario
                ) VALUES (%s, %s, %s, %s)
                """,
                (
                    alert_id,
                    "creada",
                    "nueva",
                    "Alerta generada automaticamente por el simulador de red.",
                ),
            )

        cursor.execute(
            """
            INSERT INTO publicaciones_vivo (
                origen_tipo,
                origen_nombre,
                topic_mqtt,
                nivel,
                resumen,
                payload_json
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                "monitoreo",
                point["elemento"],
                point["topic_mqtt"] or build_power_topic(profile),
                "critico" if status == "critico" else ("alerta" if status == "advertencia" else "info"),
                (
                    f"{humanize_name(point['elemento'])}: {status.upper()} | "
                    f"Voltaje {reading['voltaje_kv']} kV | Carga {reading['carga_pct']} % | "
                    f"THDi {reading['thd_i_pct']} %"
                ),
                Json(reading),
            ),
        )

    def _load_latest_point_energy(self, cursor):
        cursor.execute(
            """
            SELECT punto_id, energia_kwh
            FROM (
                SELECT
                    punto_id,
                    energia_kwh,
                    ROW_NUMBER() OVER (
                        PARTITION BY punto_id
                        ORDER BY timestamp_medicion DESC, id DESC
                    ) AS row_num
                FROM mediciones_calidad_energia
            ) ranked
            WHERE row_num = 1
            """
        )
        return {row["punto_id"]: row["energia_kwh"] for row in cursor.fetchall()}
