import os
from functools import wraps

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .config import Config
from .db import bootstrap_database, database_is_configured
from .services import (
    authenticate_user,
    fetch_alert_workflow_data,
    fetch_dashboard_data,
    fetch_live_feed,
    fetch_monitoring_snapshot,
    toggle_point,
    update_alert_workflow,
)
from .simulator import IoTSimulator


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.extensions["system_state"] = {
        "db_configured": database_is_configured(app),
        "db_ready": False,
        "db_error": None,
    }

    _initialize_runtime(app)
    _register_context(app)
    _register_routes(app)
    return app


def _initialize_runtime(app):
    state = app.extensions["system_state"]
    if not state["db_configured"]:
        state["db_error"] = (
            "Completa las variables POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER y "
            "POSTGRES_PASSWORD para habilitar el login y la simulacion."
        )
        return

    try:
        bootstrap_database(app)
        state["db_ready"] = True
    except Exception as exc:  # pragma: no cover
        app.logger.exception("No fue posible inicializar PostgreSQL: %s", exc)
        state["db_error"] = str(exc)
        return

    if app.config["SIMULATOR_ENABLED"] and _can_start_background_threads():
        simulator = IoTSimulator(app)
        simulator.start()
        app.extensions["simulator"] = simulator


def _can_start_background_threads():
    debug_enabled = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    return not debug_enabled or os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def _register_context(app):
    @app.context_processor
    def inject_shared_context():
        return {
            "current_user": session.get("user"),
            "system_state": app.extensions["system_state"],
        }


def _register_routes(app):
    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped

    def database_ready_or_503():
        state = app.extensions["system_state"]
        if state["db_ready"]:
            return None
        return (
            jsonify(
                {
                    "ok": False,
                    "message": state["db_error"] or "La base de datos no esta disponible.",
                }
            ),
            503,
        )

    @app.get("/")
    def home():
        destination = "dashboard" if session.get("user") else "login"
        return redirect(url_for(destination))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("user"):
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            if not app.extensions["system_state"]["db_ready"]:
                flash("La base de datos aun no esta lista. Revisa la configuracion de PostgreSQL.", "error")
                return render_template("login.html", page_name="login")

            user = authenticate_user(
                app,
                request.form.get("email", ""),
                request.form.get("password", ""),
            )
            if not user:
                flash("Credenciales invalidas. Verifica el correo y la contrasena.", "error")
                return render_template("login.html", page_name="login")

            session["user"] = user
            return redirect(url_for("dashboard"))

        return render_template("login.html", page_name="login")

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html", page_name="dashboard")

    @app.get("/monitoring")
    @login_required
    def monitoring():
        return render_template("monitoring.html", page_name="monitoring")

    @app.get("/alerts")
    @login_required
    def alerts():
        return render_template("alerts.html", page_name="alerts")

    @app.get("/api/system-status")
    @login_required
    def system_status():
        return jsonify({"ok": True, **app.extensions["system_state"]})

    @app.get("/api/dashboard/summary")
    @login_required
    def dashboard_summary():
        maybe_error = database_ready_or_503()
        if maybe_error:
            return maybe_error
        return jsonify({"ok": True, **fetch_dashboard_data(app)})

    @app.get("/api/monitoring")
    @login_required
    def monitoring_api():
        maybe_error = database_ready_or_503()
        if maybe_error:
            return maybe_error
        return jsonify({"ok": True, **fetch_monitoring_snapshot(app)})

    @app.post("/api/points/<int:point_id>/toggle")
    @login_required
    def toggle_point_api(point_id):
        maybe_error = database_ready_or_503()
        if maybe_error:
            return maybe_error

        point = toggle_point(app, point_id)
        if not point:
            return jsonify({"ok": False, "message": "Publisher no encontrado."}), 404
        return jsonify({"ok": True, "point": point})

    @app.get("/api/live")
    @login_required
    def live_feed_api():
        maybe_error = database_ready_or_503()
        if maybe_error:
            return maybe_error
        return jsonify({"ok": True, **fetch_live_feed(app)})

    @app.get("/api/alerts/workflow")
    @login_required
    def alert_workflow_api():
        maybe_error = database_ready_or_503()
        if maybe_error:
            return maybe_error

        selected_alert_id = request.args.get("selected_id", type=int)
        return jsonify(
            {
                "ok": True,
                **fetch_alert_workflow_data(
                    app,
                    selected_alert_id=selected_alert_id,
                ),
            }
        )

    @app.post("/api/alerts/<int:alert_id>/workflow")
    @login_required
    def update_alert_workflow_api(alert_id):
        maybe_error = database_ready_or_503()
        if maybe_error:
            return maybe_error

        payload = request.get_json(silent=True) or {}
        try:
            alert = update_alert_workflow(
                app,
                alert_id=alert_id,
                actor_user_id=session["user"]["id"],
                estado_alerta=payload.get("estado_alerta", ""),
                responsable_id=payload.get("responsable_id"),
                comentario=payload.get("comentario", ""),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

        if not alert:
            return jsonify({"ok": False, "message": "Alerta no encontrada."}), 404

        return jsonify({"ok": True, "alert": alert})
