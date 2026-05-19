import os
from pathlib import Path


def load_env_file(path):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]

        os.environ.setdefault(key, value)


load_env_file(Path(__file__).resolve().parent.parent / ".env")


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    SECRET_KEY = os.getenv("SECRET_KEY", "electiva3-dev-secret")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "").strip()
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432") or 5432)
    POSTGRES_DB = os.getenv("POSTGRES_DB", "").strip()
    POSTGRES_USER = os.getenv("POSTGRES_USER", "").strip()
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
    SIMULATION_INTERVAL = int(os.getenv("SIMULATION_INTERVAL", "5") or 5)
    SIMULATOR_ENABLED = os.getenv("SIMULATOR_ENABLED", "true").lower() == "true"
    SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"
    DEFAULT_ADMIN_NAME = "Administrador"
    DEFAULT_ADMIN_EMAIL = "admin@electiva3.com"
    DEFAULT_ADMIN_PASSWORD = "Ta.1006877358"
