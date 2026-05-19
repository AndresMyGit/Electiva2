-- ============================================================
--  ESQUEMA ELECTIVA III
--  Plataforma web IoT con PostgreSQL
-- ============================================================

CREATE TABLE IF NOT EXISTS usuarios (
    id          SERIAL PRIMARY KEY,
    nombre      VARCHAR(120) NOT NULL,
    email       VARCHAR(180) NOT NULL UNIQUE,
    password    TEXT NOT NULL,
    rol         VARCHAR(20) NOT NULL DEFAULT 'operador',
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_usuarios_rol CHECK (rol IN ('admin', 'operador', 'visor'))
);

CREATE TABLE IF NOT EXISTS dispositivos (
    id          SERIAL PRIMARY KEY,
    ciudad      VARCHAR(80) NOT NULL,
    planta      VARCHAR(80) NOT NULL,
    nombre      VARCHAR(120) NOT NULL,
    topic_mqtt  TEXT NOT NULL UNIQUE,
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lecturas_electricas (
    id              SERIAL PRIMARY KEY,
    dispositivo_id  INTEGER NOT NULL REFERENCES dispositivos (id),
    timestamp_medicion TIMESTAMP NOT NULL,
    voltaje_v       REAL NOT NULL,
    corriente_a     REAL NOT NULL,
    factor_potencia REAL NOT NULL,
    potencia_w      REAL NOT NULL,
    energia_kwh     REAL NOT NULL,
    estado_operacion VARCHAR(20) NOT NULL DEFAULT 'normal',
    detalle_alerta  TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_lecturas_estado CHECK (estado_operacion IN ('normal', 'alerta'))
);

CREATE TABLE IF NOT EXISTS puntos_monitoreo (
    id                  SERIAL PRIMARY KEY,
    zona                VARCHAR(80) NOT NULL,
    subestacion         VARCHAR(120) NOT NULL,
    circuito            VARCHAR(120) NOT NULL,
    elemento            VARCHAR(160) NOT NULL UNIQUE,
    tipo                VARCHAR(80) NOT NULL,
    voltaje_nominal_kv  REAL NOT NULL,
    topic_mqtt          TEXT NOT NULL DEFAULT '',
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE puntos_monitoreo
    ADD COLUMN IF NOT EXISTS topic_mqtt TEXT NOT NULL DEFAULT '';

ALTER TABLE puntos_monitoreo
    ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE puntos_monitoreo
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS mediciones_calidad_energia (
    id                      SERIAL PRIMARY KEY,
    punto_id                INTEGER NOT NULL REFERENCES puntos_monitoreo (id),
    topic                   TEXT NOT NULL,
    timestamp_medicion      TIMESTAMP NOT NULL,
    voltaje_kv              REAL NOT NULL,
    corriente_a             REAL NOT NULL,
    frecuencia_hz           REAL NOT NULL,
    factor_potencia         REAL NOT NULL,
    thd_v_pct               REAL NOT NULL,
    thd_i_pct               REAL NOT NULL,
    potencia_activa_kw      REAL NOT NULL,
    potencia_reactiva_kvar  REAL NOT NULL,
    potencia_aparente_kva   REAL NOT NULL,
    energia_kwh             REAL NOT NULL,
    carga_pct               REAL NOT NULL,
    estado_calidad          VARCHAR(20) NOT NULL,
    created_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_calidad_estado CHECK (estado_calidad IN ('normal', 'advertencia', 'critico'))
);

CREATE TABLE IF NOT EXISTS alertas_calidad_energia (
    id              SERIAL PRIMARY KEY,
    medicion_id     INTEGER NOT NULL REFERENCES mediciones_calidad_energia (id),
    tipo_alerta     VARCHAR(120) NOT NULL,
    detalle         TEXT NOT NULL,
    estado_alerta   VARCHAR(20) NOT NULL DEFAULT 'nueva',
    responsable_id  INTEGER REFERENCES usuarios (id),
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at     TIMESTAMP,
    CONSTRAINT chk_alerta_estado CHECK (estado_alerta IN ('nueva', 'en_revision', 'resuelta'))
);

ALTER TABLE alertas_calidad_energia
    ADD COLUMN IF NOT EXISTS estado_alerta VARCHAR(20) NOT NULL DEFAULT 'nueva';

ALTER TABLE alertas_calidad_energia
    ADD COLUMN IF NOT EXISTS responsable_id INTEGER REFERENCES usuarios (id);

ALTER TABLE alertas_calidad_energia
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE alertas_calidad_energia
    ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP;

UPDATE alertas_calidad_energia
SET
    estado_alerta = COALESCE(estado_alerta, 'nueva'),
    updated_at = COALESCE(updated_at, created_at)
WHERE estado_alerta IS NULL OR updated_at IS NULL;

CREATE TABLE IF NOT EXISTS alertas_seguimiento (
    id              SERIAL PRIMARY KEY,
    alerta_id       INTEGER NOT NULL REFERENCES alertas_calidad_energia (id) ON DELETE CASCADE,
    usuario_id      INTEGER REFERENCES usuarios (id),
    accion          VARCHAR(30) NOT NULL,
    estado_anterior VARCHAR(20),
    estado_nuevo    VARCHAR(20),
    comentario      TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alertas_seguimiento_alerta_fecha
    ON alertas_seguimiento (alerta_id, created_at DESC);

CREATE TABLE IF NOT EXISTS lecturas_ambientales (
    id              SERIAL PRIMARY KEY,
    timestamp_medicion TIMESTAMP NOT NULL,
    temperatura     REAL NOT NULL,
    humedad         REAL NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS estados_luz (
    id          SERIAL PRIMARY KEY,
    timestamp_medicion TIMESTAMP NOT NULL,
    estado      BOOLEAN NOT NULL,
    control     VARCHAR(20) NOT NULL DEFAULT 'automatico',
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_estados_luz_control CHECK (control IN ('automatico', 'manual', 'dashboard'))
);

CREATE TABLE IF NOT EXISTS publicaciones_vivo (
    id              SERIAL PRIMARY KEY,
    origen_tipo     VARCHAR(20) NOT NULL,
    origen_nombre   VARCHAR(160) NOT NULL,
    topic_mqtt      TEXT NOT NULL DEFAULT '',
    nivel           VARCHAR(20) NOT NULL DEFAULT 'info',
    resumen         TEXT NOT NULL,
    payload_json    JSONB NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_publicaciones_tipo CHECK (origen_tipo IN ('dispositivo', 'monitoreo', 'sistema')),
    CONSTRAINT chk_publicaciones_nivel CHECK (nivel IN ('info', 'alerta', 'critico'))
);

CREATE INDEX IF NOT EXISTS idx_lecturas_dispositivo_fecha
    ON lecturas_electricas (dispositivo_id, timestamp_medicion DESC);

CREATE INDEX IF NOT EXISTS idx_mediciones_punto_fecha
    ON mediciones_calidad_energia (punto_id, timestamp_medicion DESC);

CREATE INDEX IF NOT EXISTS idx_alertas_created_at
    ON alertas_calidad_energia (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alertas_estado_alerta
    ON alertas_calidad_energia (estado_alerta, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_publicaciones_created_at
    ON publicaciones_vivo (created_at DESC);

INSERT INTO alertas_seguimiento (
    alerta_id, accion, estado_nuevo, comentario, created_at
)
SELECT
    a.id,
    'creada',
    a.estado_alerta,
    'Alerta registrada antes de la activacion del flujo de gestion.',
    a.created_at
FROM alertas_calidad_energia a
WHERE NOT EXISTS (
    SELECT 1
    FROM alertas_seguimiento s
    WHERE s.alerta_id = a.id
);

INSERT INTO dispositivos (ciudad, planta, nombre, topic_mqtt, activo)
VALUES
    ('bogota', 'planta1', 'aire_acondicionado', 'empresaEnergia/bogota/planta1/aire_acondicionado/resumen', TRUE),
    ('medellin', 'planta2', 'horno_electrico', 'empresaEnergia/medellin/planta2/horno_electrico/resumen', TRUE),
    ('cali', 'planta3', 'bomba_de_agua', 'empresaEnergia/cali/planta3/bomba_de_agua/resumen', TRUE),
    ('barranquilla', 'planta4', 'nevera_industrial', 'empresaEnergia/barranquilla/planta4/nevera_industrial/resumen', TRUE)
ON CONFLICT (topic_mqtt) DO NOTHING;

INSERT INTO puntos_monitoreo (
    zona, subestacion, circuito, elemento, tipo, voltaje_nominal_kv, topic_mqtt, activo
)
VALUES
    ('bogota', 'subestacion_centro', 'circuito_principal', 'barra_principal_13_2kv', 'subestacion', 13.2, 'redDistribucion/bogota/subestacion_centro/circuito_principal/barra_principal_13_2kv/mediciones', TRUE),
    ('bogota', 'subestacion_centro', 'alimentador_norte_01', 'reconectador_norte', 'alimentador', 13.2, 'redDistribucion/bogota/subestacion_centro/alimentador_norte_01/reconectador_norte/mediciones', TRUE),
    ('bogota', 'subestacion_centro', 'alimentador_sur_02', 'reconectador_sur', 'alimentador', 13.2, 'redDistribucion/bogota/subestacion_centro/alimentador_sur_02/reconectador_sur/mediciones', TRUE),
    ('bogota', 'subestacion_centro', 'ramal_comercial_03', 'transformador_comercial_t1', 'transformador', 0.48, 'redDistribucion/bogota/subestacion_centro/ramal_comercial_03/transformador_comercial_t1/mediciones', TRUE),
    ('bogota', 'subestacion_centro', 'ramal_residencial_05', 'transformador_residencial_t2', 'transformador', 0.208, 'redDistribucion/bogota/subestacion_centro/ramal_residencial_05/transformador_residencial_t2/mediciones', TRUE)
ON CONFLICT (elemento) DO NOTHING;
