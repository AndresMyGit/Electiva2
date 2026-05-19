import math
import random
from datetime import datetime


DEVICE_PROFILES = [
    {
        "ciudad": "bogota",
        "planta": "planta1",
        "nombre": "aire_acondicionado",
        "voltaje_rango": (110.0, 125.0),
        "corriente_rango": (7.0, 12.0),
        "factor_potencia_rango": (0.88, 0.97),
    },
    {
        "ciudad": "medellin",
        "planta": "planta2",
        "nombre": "horno_electrico",
        "voltaje_rango": (215.0, 230.0),
        "corriente_rango": (10.0, 16.0),
        "factor_potencia_rango": (0.90, 0.98),
    },
    {
        "ciudad": "cali",
        "planta": "planta3",
        "nombre": "bomba_de_agua",
        "voltaje_rango": (215.0, 230.0),
        "corriente_rango": (6.0, 10.0),
        "factor_potencia_rango": (0.82, 0.93),
    },
    {
        "ciudad": "barranquilla",
        "planta": "planta4",
        "nombre": "nevera_industrial",
        "voltaje_rango": (110.0, 125.0),
        "corriente_rango": (4.0, 8.0),
        "factor_potencia_rango": (0.85, 0.95),
    },
]

POWER_POINT_PROFILES = [
    {
        "zona": "bogota",
        "subestacion": "subestacion_centro",
        "circuito": "circuito_principal",
        "elemento": "barra_principal_13_2kv",
        "tipo": "subestacion",
        "voltaje_nominal_kv": 13.2,
        "corriente_rango_a": (180.0, 280.0),
        "factor_potencia_rango": (0.96, 0.99),
        "factor_potencia_min": 0.95,
        "frecuencia_rango_hz": (59.96, 60.04),
        "thd_v_rango_pct": (1.0, 2.5),
        "thd_i_rango_pct": (2.5, 5.0),
        "thd_v_max_pct": 5.0,
        "thd_i_max_pct": 12.0,
    },
    {
        "zona": "bogota",
        "subestacion": "subestacion_centro",
        "circuito": "alimentador_norte_01",
        "elemento": "reconectador_norte",
        "tipo": "alimentador",
        "voltaje_nominal_kv": 13.2,
        "corriente_rango_a": (120.0, 210.0),
        "factor_potencia_rango": (0.92, 0.98),
        "factor_potencia_min": 0.90,
        "frecuencia_rango_hz": (59.92, 60.08),
        "thd_v_rango_pct": (1.4, 3.2),
        "thd_i_rango_pct": (3.0, 6.8),
        "thd_v_max_pct": 5.0,
        "thd_i_max_pct": 12.0,
    },
    {
        "zona": "bogota",
        "subestacion": "subestacion_centro",
        "circuito": "alimentador_sur_02",
        "elemento": "reconectador_sur",
        "tipo": "alimentador",
        "voltaje_nominal_kv": 13.2,
        "corriente_rango_a": (100.0, 195.0),
        "factor_potencia_rango": (0.90, 0.97),
        "factor_potencia_min": 0.90,
        "frecuencia_rango_hz": (59.90, 60.10),
        "thd_v_rango_pct": (1.8, 3.8),
        "thd_i_rango_pct": (3.8, 7.2),
        "thd_v_max_pct": 5.0,
        "thd_i_max_pct": 12.0,
    },
    {
        "zona": "bogota",
        "subestacion": "subestacion_centro",
        "circuito": "ramal_comercial_03",
        "elemento": "transformador_comercial_t1",
        "tipo": "transformador",
        "voltaje_nominal_kv": 0.48,
        "corriente_rango_a": (180.0, 320.0),
        "factor_potencia_rango": (0.88, 0.96),
        "factor_potencia_min": 0.88,
        "frecuencia_rango_hz": (59.88, 60.12),
        "thd_v_rango_pct": (2.0, 4.5),
        "thd_i_rango_pct": (4.5, 8.5),
        "thd_v_max_pct": 6.0,
        "thd_i_max_pct": 15.0,
    },
    {
        "zona": "bogota",
        "subestacion": "subestacion_centro",
        "circuito": "ramal_residencial_05",
        "elemento": "transformador_residencial_t2",
        "tipo": "transformador",
        "voltaje_nominal_kv": 0.208,
        "corriente_rango_a": (90.0, 170.0),
        "factor_potencia_rango": (0.84, 0.94),
        "factor_potencia_min": 0.85,
        "frecuencia_rango_hz": (59.88, 60.12),
        "thd_v_rango_pct": (2.5, 4.8),
        "thd_i_rango_pct": (5.0, 9.0),
        "thd_v_max_pct": 6.0,
        "thd_i_max_pct": 15.0,
    },
]

DEVICE_PROFILE_MAP = {item["nombre"]: item for item in DEVICE_PROFILES}
POWER_POINT_PROFILE_MAP = {item["elemento"]: item for item in POWER_POINT_PROFILES}


def build_device_topic(profile):
    return (
        f"empresaEnergia/{profile['ciudad']}/{profile['planta']}/"
        f"{profile['nombre']}/resumen"
    )


def build_power_topic(profile):
    return (
        f"redDistribucion/{profile['zona']}/{profile['subestacion']}/"
        f"{profile['circuito']}/{profile['elemento']}/mediciones"
    )


def humanize_name(value):
    return value.replace("_", " ").title()


def _generate_value(
    value_range,
    prob_anomaly=0.15,
    allow_low=True,
    allow_high=True,
    low_margin=0.9,
    high_margin=1.1,
):
    minimum, maximum = value_range
    value = random.uniform(minimum, maximum)

    if random.random() < prob_anomaly:
        if allow_high and (not allow_low or random.choice([True, False])):
            value = random.uniform(maximum * 1.01, maximum * high_margin)
        elif allow_low:
            value = random.uniform(minimum * low_margin, minimum * 0.99)

    return round(value, 4)


def generate_device_reading(profile, energy_base=0.0, interval_seconds=5):
    voltage = _generate_value(
        profile["voltaje_rango"],
        prob_anomaly=0.12,
        low_margin=0.88,
        high_margin=1.12,
    )
    current = _generate_value(
        profile["corriente_rango"],
        prob_anomaly=0.18,
        allow_low=False,
        high_margin=1.18,
    )
    factor = round(random.uniform(*profile["factor_potencia_rango"]), 2)
    power = round(voltage * current * factor, 2)
    energy = round(energy_base + ((power / 1000) * (interval_seconds / 3600)), 4)

    return {
        "timestamp": datetime.now().replace(microsecond=0).isoformat(),
        "voltaje_v": round(voltage, 2),
        "corriente_a": round(current, 2),
        "factor_potencia": factor,
        "potencia_w": power,
        "energia_kwh": energy,
    }


def evaluate_device_reading(reading, profile):
    alerts = []
    min_voltage, max_voltage = profile["voltaje_rango"]
    _, max_current = profile["corriente_rango"]
    min_factor, _ = profile["factor_potencia_rango"]

    if reading["voltaje_v"] < min_voltage or reading["voltaje_v"] > max_voltage:
        alerts.append(
            f"Voltaje fuera de rango ({reading['voltaje_v']} V, esperado {min_voltage}-{max_voltage} V)"
        )
    if reading["corriente_a"] > max_current:
        alerts.append(
            f"Sobreconsumo detectado ({reading['corriente_a']} A, maximo {max_current} A)"
        )
    if reading["factor_potencia"] < min_factor:
        alerts.append(
            f"Factor de potencia bajo ({reading['factor_potencia']}, minimo {min_factor})"
        )

    status = "alerta" if alerts else "normal"
    return status, alerts


def get_power_limits(profile):
    nominal_voltage = profile["voltaje_nominal_kv"]
    return {
        "voltaje_min_kv": round(nominal_voltage * 0.95, 4),
        "voltaje_max_kv": round(nominal_voltage * 1.05, 4),
        "corriente_max_a": profile["corriente_rango_a"][1],
        "frecuencia_min_hz": 59.5,
        "frecuencia_max_hz": 60.5,
        "factor_potencia_min": profile["factor_potencia_min"],
        "thd_v_max_pct": profile["thd_v_max_pct"],
        "thd_i_max_pct": profile["thd_i_max_pct"],
        "carga_max_pct": 100.0,
    }


def generate_power_quality_reading(profile, energy_base=0.0, interval_seconds=5):
    nominal_voltage = profile["voltaje_nominal_kv"]
    voltage_kv = _generate_value(
        (nominal_voltage * 0.98, nominal_voltage * 1.02),
        prob_anomaly=0.12,
        low_margin=0.9,
        high_margin=1.1,
    )
    current = _generate_value(
        profile["corriente_rango_a"],
        prob_anomaly=0.18,
        allow_low=False,
        high_margin=1.15,
    )
    frequency = _generate_value(
        profile["frecuencia_rango_hz"],
        prob_anomaly=0.08,
        low_margin=0.99,
        high_margin=1.01,
    )
    factor = _generate_value(
        profile["factor_potencia_rango"],
        prob_anomaly=0.15,
        allow_high=False,
        low_margin=0.88,
    )
    thd_v = _generate_value(
        profile["thd_v_rango_pct"],
        prob_anomaly=0.12,
        allow_low=False,
        high_margin=1.8,
    )
    thd_i = _generate_value(
        profile["thd_i_rango_pct"],
        prob_anomaly=0.15,
        allow_low=False,
        high_margin=1.8,
    )

    apparent_power = round(math.sqrt(3) * voltage_kv * current, 2)
    active_power = round(apparent_power * factor, 2)
    reactive_power = round(
        math.sqrt(max((apparent_power ** 2) - (active_power ** 2), 0)),
        2,
    )
    load_pct = round((current / profile["corriente_rango_a"][1]) * 100, 2)
    energy = round(energy_base + (active_power * (interval_seconds / 3600)), 4)

    return {
        "timestamp": datetime.now().replace(microsecond=0).isoformat(),
        "voltaje_kv": round(voltage_kv, 4),
        "corriente_a": round(current, 4),
        "frecuencia_hz": round(frequency, 4),
        "factor_potencia": round(factor, 4),
        "thd_v_pct": round(thd_v, 4),
        "thd_i_pct": round(thd_i, 4),
        "potencia_activa_kw": active_power,
        "potencia_reactiva_kvar": reactive_power,
        "potencia_aparente_kva": apparent_power,
        "energia_kwh": energy,
        "carga_pct": load_pct,
    }


def evaluate_power_quality(reading, profile):
    limits = get_power_limits(profile)
    alerts = []

    if not limits["voltaje_min_kv"] <= reading["voltaje_kv"] <= limits["voltaje_max_kv"]:
        alerts.append(
            (
                "voltaje_fuera_de_rango",
                f"Voltaje medido {reading['voltaje_kv']} kV, rango permitido "
                f"{limits['voltaje_min_kv']} - {limits['voltaje_max_kv']} kV",
            )
        )
    if reading["corriente_a"] > limits["corriente_max_a"]:
        alerts.append(
            (
                "sobrecorriente",
                f"Corriente medida {reading['corriente_a']} A, maximo permitido "
                f"{limits['corriente_max_a']} A",
            )
        )
    if not limits["frecuencia_min_hz"] <= reading["frecuencia_hz"] <= limits["frecuencia_max_hz"]:
        alerts.append(
            (
                "frecuencia_anormal",
                f"Frecuencia medida {reading['frecuencia_hz']} Hz, rango permitido "
                f"{limits['frecuencia_min_hz']} - {limits['frecuencia_max_hz']} Hz",
            )
        )
    if reading["factor_potencia"] < limits["factor_potencia_min"]:
        alerts.append(
            (
                "bajo_factor_potencia",
                f"Factor de potencia medido {reading['factor_potencia']}, minimo permitido "
                f"{limits['factor_potencia_min']}",
            )
        )
    if reading["thd_v_pct"] > limits["thd_v_max_pct"]:
        alerts.append(
            (
                "thd_voltaje_alto",
                f"THD de voltaje medido {reading['thd_v_pct']} %, maximo permitido "
                f"{limits['thd_v_max_pct']} %",
            )
        )
    if reading["thd_i_pct"] > limits["thd_i_max_pct"]:
        alerts.append(
            (
                "thd_corriente_alto",
                f"THD de corriente medido {reading['thd_i_pct']} %, maximo permitido "
                f"{limits['thd_i_max_pct']} %",
            )
        )
    if reading["carga_pct"] > limits["carga_max_pct"]:
        alerts.append(
            (
                "sobrecarga",
                f"Nivel de carga medido {reading['carga_pct']} %, maximo permitido "
                f"{limits['carga_max_pct']} %",
            )
        )

    if not alerts:
        status = "normal"
    else:
        severe_voltage = (
            reading["voltaje_kv"] < profile["voltaje_nominal_kv"] * 0.92
            or reading["voltaje_kv"] > profile["voltaje_nominal_kv"] * 1.08
        )
        severe_current = reading["corriente_a"] > limits["corriente_max_a"] * 1.1
        severe_thd = reading["thd_i_pct"] > limits["thd_i_max_pct"] * 1.3
        status = "critico" if len(alerts) > 1 or severe_voltage or severe_current or severe_thd else "advertencia"

    return status, alerts

