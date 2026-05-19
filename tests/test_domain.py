import unittest

from app.domain import (
    DEVICE_PROFILE_MAP,
    POWER_POINT_PROFILE_MAP,
    evaluate_device_reading,
    evaluate_power_quality,
    generate_device_reading,
    generate_power_quality_reading,
)


class DomainTests(unittest.TestCase):
    def test_generate_device_reading_contains_expected_fields(self):
        reading = generate_device_reading(DEVICE_PROFILE_MAP["aire_acondicionado"], 1.2, 5)
        self.assertIn("voltaje_v", reading)
        self.assertIn("corriente_a", reading)
        self.assertGreater(reading["energia_kwh"], 1.2)

    def test_device_alert_detection(self):
        profile = DEVICE_PROFILE_MAP["horno_electrico"]
        status, alerts = evaluate_device_reading(
            {
                "voltaje_v": 240.0,
                "corriente_a": 18.0,
                "factor_potencia": 0.85,
                "potencia_w": 0,
                "energia_kwh": 0,
            },
            profile,
        )
        self.assertEqual(status, "alerta")
        self.assertGreaterEqual(len(alerts), 2)

    def test_power_quality_reading_and_evaluation(self):
        profile = POWER_POINT_PROFILE_MAP["reconectador_norte"]
        reading = generate_power_quality_reading(profile, 25.0, 5)
        self.assertGreater(reading["energia_kwh"], 25.0)

        status, alerts = evaluate_power_quality(
            {
                **reading,
                "voltaje_kv": 15.5,
                "carga_pct": 118.0,
                "thd_i_pct": 22.0,
            },
            profile,
        )
        self.assertIn(status, {"advertencia", "critico"})
        self.assertTrue(alerts)


if __name__ == "__main__":
    unittest.main()
