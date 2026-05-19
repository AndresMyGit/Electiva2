# Electiva III IoT Dashboard

Aplicacion web reconstruida con Flask y PostgreSQL para monitoreo IoT. Incluye:

- Login con sesion y usuario administrador inicial.
- Dashboard con resumen operativo y publicaciones recientes.
- Vista de monitoreo con estado por publisher, pausa/reactivacion y graficas.
- Vista de alertas con flujo completo, responsable, comentarios e historial de publicaciones en vivo.
- Simulacion periodica del proyecto de red de distribucion electrica.

## Stack

- Python 3.14
- Flask
- PostgreSQL
- `psycopg2`
- HTML, CSS y JavaScript sin frameworks pesados

## Configuracion

1. Crea una base de datos PostgreSQL vacia.
2. Copia `.env.example` a `.env` o define las variables del entorno manualmente.
3. Completa estas variables:

```env
SECRET_KEY=
POSTGRES_HOST=
POSTGRES_PORT=5432
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
SIMULATION_INTERVAL=5
SIMULATOR_ENABLED=true
FLASK_DEBUG=false
PORT=5000
```

4. Instala dependencias:

```powershell
python -m pip install -r requirements.txt
```

5. Inicia la aplicacion:

```powershell
python app.py
```

La app intentara inicializar automaticamente el esquema de [database/schema.sql](database/schema.sql) cuando PostgreSQL este configurado.

## Credenciales iniciales

- Correo: `admin@electiva3.com`
- Contrasena: `Ta.1006877358`

Ese usuario se crea automaticamente en el primer arranque y la contrasena se guarda con hash.

## SQL agregado

Ademas del esquema base, se ampliaron estos elementos:

- Tabla `publicaciones_vivo` para el historial de mensajes y eventos del sistema.
- Tabla `alertas_seguimiento` para registrar cambios de estado, comentarios y actor del seguimiento.
- Columnas `topic_mqtt`, `activo` y `updated_at` en `puntos_monitoreo` para controlar cada publisher del proyecto.
- Columnas `estado_alerta`, `responsable_id`, `updated_at` y `resolved_at` en `alertas_calidad_energia` para el flujo operativo.
- Columnas `estado_operacion` y `detalle_alerta` en `lecturas_electricas` para marcar si un dispositivo esta en alerta.
- `updated_at` en `dispositivos` para compatibilidad con la version anterior del proyecto.

## Estructura principal

```text
app/
  static/
  templates/
  __init__.py
  config.py
  db.py
  domain.py
  services.py
  simulator.py
database/
  schema.sql
tests/
  test_domain.py
app.py
```

## Verificacion rapida

Para validar la logica pura sin depender de PostgreSQL:

```powershell
python -m unittest discover -s tests
```
