from collections import defaultdict
from datetime import datetime

from psycopg2.extras import Json, RealDictCursor
from werkzeug.security import check_password_hash

from .db import get_connection
from .domain import humanize_name


ALERT_WORKFLOW_STATES = {"nueva", "en_revision", "resuelta"}


def _serialize(value):
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return value


def _serialize_row(row):
    return {key: _serialize(value) for key, value in row.items()}


def _normalize_optional_int(value):
    if value in (None, "", "null", "None", 0, "0"):
        return None
    return int(value)


def _workflow_label(status):
    labels = {
        "nueva": "Nueva",
        "en_revision": "En revision",
        "resuelta": "Resuelta",
    }
    return labels.get(status, "Sin estado")


def authenticate_user(app, email, password):
    normalized_email = email.strip().lower()
    with get_connection(app) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT id, nombre, email, password, rol, activo
                FROM usuarios
                WHERE email = %s
                """,
                (normalized_email,),
            )
            user = cursor.fetchone()

    if not user or not user["activo"]:
        return None
    if not check_password_hash(user["password"], password):
        return None

    return {
        "id": user["id"],
        "nombre": user["nombre"],
        "email": user["email"],
        "rol": user["rol"],
    }


def fetch_dashboard_data(app):
    points = fetch_monitoring_snapshot(app, history_limit=8)["points"]
    alerts = fetch_recent_alerts(app, limit=6)
    publications = fetch_recent_publications(app, limit=8)

    active_publishers = sum(1 for item in points if item["activo"])
    paused_publishers = sum(1 for item in points if not item["activo"])
    warning_points = sum(1 for item in points if item["status"] == "advertencia")
    critical_points = sum(1 for item in points if item["status"] == "critico")
    publication_volume = _fetch_publication_volume(app)
    alerts_last_day = _fetch_alert_total_last_day(app)

    latest_load = [
        item["last_reading"]["carga_pct"]
        for item in points
        if item["last_reading"] and item["status"] != "apagado"
    ]
    latest_energy = [
        item["last_reading"]["energia_kwh"]
        for item in points
        if item["last_reading"]
    ]

    summary = {
        "active_publishers": active_publishers,
        "paused_publishers": paused_publishers,
        "warning_points": warning_points,
        "critical_points": critical_points,
        "publications_last_hour": publication_volume,
        "alerts_last_24h": alerts_last_day,
        "avg_load_pct": round(sum(latest_load) / len(latest_load), 2) if latest_load else 0,
        "total_energy_kwh": round(sum(latest_energy), 2) if latest_energy else 0,
    }

    return {
        "summary": summary,
        "points": points,
        "recent_alerts": alerts,
        "recent_publications": publications,
    }


def fetch_monitoring_snapshot(app, history_limit=18):
    with get_connection(app) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    p.id,
                    p.zona,
                    p.subestacion,
                    p.circuito,
                    p.elemento,
                    p.tipo,
                    p.topic_mqtt,
                    p.activo,
                    latest.medicion_id,
                    latest.timestamp_medicion,
                    latest.voltaje_kv,
                    latest.corriente_a,
                    latest.frecuencia_hz,
                    latest.factor_potencia,
                    latest.thd_v_pct,
                    latest.thd_i_pct,
                    latest.potencia_activa_kw,
                    latest.potencia_reactiva_kvar,
                    latest.potencia_aparente_kva,
                    latest.energia_kwh,
                    latest.carga_pct,
                    latest.estado_calidad,
                    latest_alert.detalle_alerta
                FROM puntos_monitoreo p
                LEFT JOIN LATERAL (
                    SELECT
                        id AS medicion_id,
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
                    FROM mediciones_calidad_energia m
                    WHERE m.punto_id = p.id
                    ORDER BY m.timestamp_medicion DESC, m.id DESC
                    LIMIT 1
                ) latest ON TRUE
                LEFT JOIN LATERAL (
                    SELECT STRING_AGG(a.detalle, ' | ' ORDER BY a.created_at DESC, a.id DESC) AS detalle_alerta
                    FROM alertas_calidad_energia a
                    WHERE a.medicion_id = latest.medicion_id
                ) latest_alert ON TRUE
                ORDER BY p.id
                """
            )
            points = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    punto_id,
                    timestamp_medicion,
                    voltaje_kv,
                    corriente_a,
                    carga_pct,
                    thd_i_pct,
                    potencia_activa_kw,
                    estado_calidad
                FROM (
                    SELECT
                        punto_id,
                        timestamp_medicion,
                        voltaje_kv,
                        corriente_a,
                        carga_pct,
                        thd_i_pct,
                        potencia_activa_kw,
                        estado_calidad,
                        ROW_NUMBER() OVER (
                            PARTITION BY punto_id
                            ORDER BY timestamp_medicion DESC, id DESC
                        ) AS row_num
                    FROM mediciones_calidad_energia
                ) ranked
                WHERE row_num <= %s
                ORDER BY punto_id, timestamp_medicion ASC
                """,
                (history_limit,),
            )
            history_rows = cursor.fetchall()

    history_by_point = defaultdict(list)
    for row in history_rows:
        history_by_point[row["punto_id"]].append(_serialize_row(dict(row)))

    payload = []
    for row in points:
        point = _serialize_row(dict(row))
        status = "apagado" if not point["activo"] else (point["estado_calidad"] or "sin_datos")
        last_reading = None
        if point["timestamp_medicion"]:
            last_reading = {
                "timestamp": point["timestamp_medicion"],
                "voltaje_kv": point["voltaje_kv"],
                "corriente_a": point["corriente_a"],
                "frecuencia_hz": point["frecuencia_hz"],
                "factor_potencia": point["factor_potencia"],
                "thd_v_pct": point["thd_v_pct"],
                "thd_i_pct": point["thd_i_pct"],
                "potencia_activa_kw": point["potencia_activa_kw"],
                "potencia_reactiva_kvar": point["potencia_reactiva_kvar"],
                "potencia_aparente_kva": point["potencia_aparente_kva"],
                "energia_kwh": point["energia_kwh"],
                "carga_pct": point["carga_pct"],
                "alert_detail": point["detalle_alerta"],
            }

        payload.append(
            {
                "id": point["id"],
                "nombre": point["elemento"],
                "display_name": humanize_name(point["elemento"]),
                "tipo": humanize_name(point["tipo"]),
                "zona": humanize_name(point["zona"]),
                "subestacion": humanize_name(point["subestacion"]),
                "circuito": humanize_name(point["circuito"]),
                "topic_mqtt": point["topic_mqtt"],
                "activo": point["activo"],
                "status": status,
                "last_reading": last_reading,
                "history": history_by_point.get(point["id"], []),
            }
        )

    return {"points": payload}


def fetch_recent_alerts(app, limit=20):
    with get_connection(app) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            return [_serialize_row(dict(row)) for row in _fetch_alert_rows(cursor, limit=limit)]


def fetch_recent_publications(app, limit=25):
    with get_connection(app) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    origen_tipo,
                    origen_nombre,
                    topic_mqtt,
                    nivel,
                    resumen,
                    payload_json,
                    created_at
                FROM publicaciones_vivo
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [_serialize_row(dict(row)) for row in cursor.fetchall()]


def fetch_live_feed(app):
    alerts = fetch_recent_alerts(app, limit=25)
    publications = fetch_recent_publications(app, limit=30)
    summary = _build_alert_summary(alerts)
    summary["total_publications"] = len(publications)

    return {
        "summary": summary,
        "alerts": alerts,
        "publications": publications,
    }


def fetch_alert_workflow_data(app, selected_alert_id=None, limit=25):
    with get_connection(app) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            alerts = [_serialize_row(dict(row)) for row in _fetch_alert_rows(cursor, limit=limit)]
            users = [_serialize_row(dict(row)) for row in _fetch_active_users(cursor)]
            publications = [_serialize_row(dict(row)) for row in _fetch_publications(cursor, limit=18)]

            if alerts:
                selected_id = int(selected_alert_id) if selected_alert_id else alerts[0]["id"]
                selected_alert = _fetch_alert_detail(cursor, selected_id)
                if selected_alert is None:
                    selected_alert = _fetch_alert_detail(cursor, alerts[0]["id"])
            else:
                selected_alert = None

    summary = _build_alert_summary(alerts)
    summary["total_publications"] = len(publications)

    return {
        "summary": summary,
        "alerts": alerts,
        "users": users,
        "selected_alert": selected_alert,
        "publications": publications,
    }


def update_alert_workflow(app, alert_id, actor_user_id, estado_alerta, responsable_id, comentario):
    if estado_alerta not in ALERT_WORKFLOW_STATES:
        raise ValueError("El estado de alerta no es valido.")

    responsible_user_id = _normalize_optional_int(responsable_id)
    note = (comentario or "").strip()

    with get_connection(app) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            current = _fetch_alert_detail(cursor, alert_id)
            if current is None:
                return None

            actor = _fetch_user(cursor, actor_user_id)
            if actor is None or not actor["activo"]:
                raise ValueError("El usuario actual no esta disponible para gestionar alertas.")

            responsible_user = None
            if responsible_user_id is not None:
                responsible_user = _fetch_user(cursor, responsible_user_id)
                if responsible_user is None or not responsible_user["activo"]:
                    raise ValueError("El responsable seleccionado no esta disponible.")

            current_state = current["estado_alerta"] or "nueva"
            current_responsible_id = current["responsable_id"]
            current_responsible_name = current["responsable_nombre"] if current_responsible_id else None
            state_changed = estado_alerta != current_state
            responsible_changed = responsible_user_id != current_responsible_id

            if not state_changed and not responsible_changed and not note:
                raise ValueError("No hay cambios para registrar en la alerta.")

            resolved_at = current["resolved_at"]
            if state_changed and estado_alerta == "resuelta":
                resolved_at = datetime.now()
            elif state_changed and current_state == "resuelta" and estado_alerta != "resuelta":
                resolved_at = None

            cursor.execute(
                """
                UPDATE alertas_calidad_energia
                SET
                    estado_alerta = %s,
                    responsable_id = %s,
                    updated_at = CURRENT_TIMESTAMP,
                    resolved_at = %s
                WHERE id = %s
                """,
                (
                    estado_alerta,
                    responsible_user_id,
                    resolved_at,
                    alert_id,
                ),
            )

            action = "comentario"
            auto_notes = []

            if state_changed and responsible_changed:
                action = "actualizacion"
            elif state_changed:
                action = "cambio_estado"
            elif responsible_changed and responsible_user_id is None:
                action = "liberacion"
            elif responsible_changed:
                action = "asignacion" if current_responsible_id is None else "reasignacion"

            if state_changed:
                auto_notes.append(
                    f"Estado cambiado de {_workflow_label(current_state)} a {_workflow_label(estado_alerta)}."
                )

            if responsible_changed:
                if responsible_user is not None:
                    auto_notes.append(f"Responsable asignado a {responsible_user['nombre']}.")
                elif current_responsible_name:
                    auto_notes.append(f"Responsable liberado. Antes estaba asignado a {current_responsible_name}.")
                else:
                    auto_notes.append("La alerta quedo sin responsable asignado.")

            if note:
                auto_notes.append(note)

            tracking_comment = " ".join(auto_notes).strip()

            cursor.execute(
                """
                INSERT INTO alertas_seguimiento (
                    alerta_id,
                    usuario_id,
                    accion,
                    estado_anterior,
                    estado_nuevo,
                    comentario
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    alert_id,
                    actor_user_id,
                    action,
                    current_state,
                    estado_alerta,
                    tracking_comment,
                ),
            )

            publication_level = "info" if estado_alerta == "resuelta" else "alerta"
            publication_summary = (
                f"Flujo de alerta {humanize_name(current['tipo_alerta'])} en "
                f"{humanize_name(current['elemento'])}: {_workflow_label(estado_alerta)}."
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
                    "sistema",
                    current["elemento"],
                    current["topic_mqtt"] or "",
                    publication_level,
                    publication_summary,
                    Json(
                        {
                            "alerta_id": alert_id,
                            "estado_alerta": estado_alerta,
                            "responsable_id": responsible_user_id,
                            "actor": actor["nombre"],
                            "comentario": tracking_comment,
                        }
                    ),
                ),
            )

            updated_alert = _fetch_alert_detail(cursor, alert_id)
        connection.commit()

    return updated_alert


def toggle_point(app, point_id):
    with get_connection(app) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                UPDATE puntos_monitoreo
                SET activo = NOT activo, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, elemento, tipo, subestacion, circuito, topic_mqtt, activo
                """,
                (point_id,),
            )
            point = cursor.fetchone()
            if not point:
                return None

            action = "reactivado" if point["activo"] else "apagado"
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
                    "sistema",
                    point["elemento"],
                    point["topic_mqtt"],
                    "info",
                    f"El publisher {humanize_name(point['elemento'])} fue {action} manualmente.",
                    Json(
                        {
                            "point_id": point["id"],
                            "estado": "activo" if point["activo"] else "apagado",
                            "subestacion": point["subestacion"],
                            "circuito": point["circuito"],
                        }
                    ),
                ),
            )
        connection.commit()

    result = _serialize_row(dict(point))
    result["display_name"] = humanize_name(result["elemento"])
    return result


def _fetch_alert_rows(cursor, limit=20):
    cursor.execute(
        """
        SELECT
            a.id,
            a.tipo_alerta,
            a.detalle,
            a.estado_alerta,
            a.responsable_id,
            a.created_at,
            a.updated_at,
            a.resolved_at,
            COALESCE(u.nombre, 'Sin asignar') AS responsable_nombre,
            p.elemento,
            p.subestacion,
            p.circuito,
            p.topic_mqtt,
            m.estado_calidad,
            m.timestamp_medicion,
            m.voltaje_kv,
            m.carga_pct,
            m.thd_i_pct
        FROM alertas_calidad_energia a
        JOIN mediciones_calidad_energia m ON m.id = a.medicion_id
        JOIN puntos_monitoreo p ON p.id = m.punto_id
        LEFT JOIN usuarios u ON u.id = a.responsable_id
        ORDER BY
            CASE a.estado_alerta
                WHEN 'nueva' THEN 0
                WHEN 'en_revision' THEN 1
                ELSE 2
            END,
            a.created_at DESC,
            a.id DESC
        LIMIT %s
        """,
        (limit,),
    )
    return cursor.fetchall()


def _fetch_alert_detail(cursor, alert_id):
    cursor.execute(
        """
        SELECT
            a.id,
            a.tipo_alerta,
            a.detalle,
            a.estado_alerta,
            a.responsable_id,
            a.created_at,
            a.updated_at,
            a.resolved_at,
            COALESCE(u.nombre, 'Sin asignar') AS responsable_nombre,
            p.elemento,
            p.subestacion,
            p.circuito,
            p.topic_mqtt,
            m.estado_calidad,
            m.timestamp_medicion,
            m.voltaje_kv,
            m.corriente_a,
            m.factor_potencia,
            m.thd_i_pct,
            m.thd_v_pct,
            m.carga_pct,
            m.potencia_activa_kw
        FROM alertas_calidad_energia a
        JOIN mediciones_calidad_energia m ON m.id = a.medicion_id
        JOIN puntos_monitoreo p ON p.id = m.punto_id
        LEFT JOIN usuarios u ON u.id = a.responsable_id
        WHERE a.id = %s
        """,
        (alert_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    payload = _serialize_row(dict(row))
    payload["timeline"] = [_serialize_row(dict(item)) for item in _fetch_alert_timeline(cursor, alert_id)]
    return payload


def _fetch_alert_timeline(cursor, alert_id):
    cursor.execute(
        """
        SELECT
            s.id,
            s.accion,
            s.estado_anterior,
            s.estado_nuevo,
            s.comentario,
            s.created_at,
            COALESCE(u.nombre, 'Sistema') AS actor_nombre
        FROM alertas_seguimiento s
        LEFT JOIN usuarios u ON u.id = s.usuario_id
        WHERE s.alerta_id = %s
        ORDER BY s.created_at DESC, s.id DESC
        LIMIT 25
        """,
        (alert_id,),
    )
    return cursor.fetchall()


def _fetch_active_users(cursor):
    cursor.execute(
        """
        SELECT id, nombre, email, rol
        FROM usuarios
        WHERE activo = TRUE
        ORDER BY nombre ASC
        """
    )
    return cursor.fetchall()


def _fetch_user(cursor, user_id):
    if user_id is None:
        return None

    cursor.execute(
        """
        SELECT id, nombre, email, rol, activo
        FROM usuarios
        WHERE id = %s
        """,
        (user_id,),
    )
    return cursor.fetchone()


def _fetch_publications(cursor, limit=18):
    cursor.execute(
        """
        SELECT
            id,
            origen_tipo,
            origen_nombre,
            topic_mqtt,
            nivel,
            resumen,
            payload_json,
            created_at
        FROM publicaciones_vivo
        ORDER BY created_at DESC, id DESC
        LIMIT %s
        """,
        (limit,),
    )
    return cursor.fetchall()


def _build_alert_summary(alerts):
    return {
        "critical_alerts": sum(
            1 for item in alerts if item["estado_calidad"] == "critico" and item["estado_alerta"] != "resuelta"
        ),
        "warning_alerts": sum(
            1 for item in alerts if item["estado_calidad"] == "advertencia" and item["estado_alerta"] != "resuelta"
        ),
        "new_alerts": sum(1 for item in alerts if item["estado_alerta"] == "nueva"),
        "in_review_alerts": sum(1 for item in alerts if item["estado_alerta"] == "en_revision"),
        "resolved_alerts": sum(1 for item in alerts if item["estado_alerta"] == "resuelta"),
    }


def _fetch_publication_volume(app):
    with get_connection(app) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM publicaciones_vivo
                WHERE created_at >= NOW() - INTERVAL '1 hour'
                """
            )
            row = cursor.fetchone()
            return row["total"] if row else 0


def _fetch_alert_total_last_day(app):
    with get_connection(app) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM alertas_calidad_energia
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                """
            )
            row = cursor.fetchone()
            return row["total"] if row else 0
