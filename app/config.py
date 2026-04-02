import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    # Secrets
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")

    # Flask/SQLAlchemy
    # Use an absolute path so SQLite doesn't depend on the current working directory.
    default_sqlite_path = (BASE_DIR / "instance" / "app.sqlite").as_posix()

    _raw_database_url = os.environ.get("DATABASE_URL")
    if _raw_database_url:
        if _raw_database_url.startswith("sqlite:///"):
            # Normalize relative sqlite paths (e.g. sqlite:///instance/app.sqlite)
            # into an absolute project-local path.
            db_path_str = _raw_database_url[len("sqlite:///") :]
            db_path = Path(db_path_str)
            if not db_path.is_absolute():
                db_path = BASE_DIR / db_path
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path.as_posix()}"
        else:
            SQLALCHEMY_DATABASE_URI = _raw_database_url
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{default_sqlite_path}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", "20")) * 1024 * 1024
    # Allowed extensions (checked server-side)
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "ogg"}
    ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "ogg"}
    ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "txt", "doc", "docx"}

    # Files
    _raw_upload_folder = os.environ.get("UPLOAD_FOLDER")
    if _raw_upload_folder:
        upload_path = Path(_raw_upload_folder)
        if not upload_path.is_absolute():
            upload_path = BASE_DIR / upload_path
        UPLOAD_FOLDER = str(upload_path)
    else:
        UPLOAD_FOLDER = str(BASE_DIR / "instance" / "uploads")

    # Time/Notifications
    # Scheduler runs every N seconds. Increase carefully for scale.
    NOTIFICATION_SCAN_INTERVAL_SECONDS = int(os.environ.get("NOTIFICATION_SCAN_INTERVAL_SECONDS", "30"))

    # Optional email
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "1") == "1"
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME or "no-reply@example.com")

    # Timezone behavior
    # Capsules are stored in UTC in DB. UI inputs are interpreted using provided client offset.
    DEFAULT_USER_TIMEZONE = os.environ.get("DEFAULT_USER_TIMEZONE", "UTC")

    # Feature flags
    ENABLE_EMAIL_NOTIFICATIONS = os.environ.get("ENABLE_EMAIL_NOTIFICATIONS", "0") == "1"


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False

