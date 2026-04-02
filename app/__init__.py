import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask

from .config import Config
from .extensions import bcrypt, csrf, db, login_manager, mail


def create_app(test_config=None):
    # Templates live in the repository-level `templates/` folder.
    app = Flask(__name__, instance_relative_config=True, template_folder="../templates")
    app.config.from_object(Config)
    if test_config:
        if isinstance(test_config, dict):
            app.config.update(test_config)
        else:
            app.config.from_object(test_config)

    # Ensure instance subdirs exist
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if isinstance(db_uri, str) and db_uri.startswith("sqlite:///"):
        # sqlite:///absolute/path OR sqlite:///relative/path
        db_path_str = db_uri[len("sqlite:///") :]
        try:
            db_path = Path(db_path_str)
            if db_path.parent:
                os.makedirs(db_path.parent, exist_ok=True)
        except Exception:
            # If parsing fails, we still create upload/instance dirs below.
            pass

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Init extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"

    # Import and register blueprints
    from .routes.auth import bp as auth_bp
    from .routes.capsules import bp as capsules_bp
    from .routes.admin import bp as admin_bp
    from .routes.share import bp as share_bp
    from .routes.notifications import bp as notifications_bp
    from .routes.profile import bp as profile_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(capsules_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(share_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(profile_bp)

    # Import models so Flask-SQLAlchemy knows about them
    from .models import User  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User

        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # Create tables on startup (simple deliverable; production should use migrations)
    @app.before_request
    def _ensure_tables_exist():
        if not getattr(app, "_db_initialized", False):
            db.create_all()
            app._db_initialized = True

    # Add a lightweight healthcheck
    @app.get("/healthz")
    def healthz():
        return {
            "ok": True,
            "server_time_utc": datetime.now(timezone.utc).isoformat(),
        }

    # Scheduler is started lazily on first request to avoid side effects in tests.
    from .services.notifications import start_notification_scheduler
    from .services.notifications import scan_and_notify

    @app.before_request
    def _start_scheduler_once():
        # The scheduler is process-local; it scans for due capsules and creates notification records.
        if app.config.get("TESTING"):
            return
        if not getattr(app, "_scheduler_started", False):
            start_notification_scheduler(app)
            app._scheduler_started = True

    @app.before_request
    def _scan_due_notifications_fallback():
        # If the background job hasn't run yet (or server just started),
        # scan opportunistically at a low frequency.
        if app.config.get("TESTING"):
            return
        interval = int(app.config["NOTIFICATION_SCAN_INTERVAL_SECONDS"])
        last = getattr(app, "_last_due_scan_at_utc", None)
        now = datetime.now(timezone.utc)
        if last is None or (now - last).total_seconds() >= interval:
            try:
                scan_and_notify(app)
            except Exception:
                app.logger.exception("Due-capsule notification scan failed")
            app._last_due_scan_at_utc = now

    return app

