import sys


# SQLAlchemy (used by Flask-SQLAlchemy) currently fails to import on Python 3.14
# in some environments. Fail fast with a clear message so you can switch
# to a compatible Python interpreter.
if sys.version_info >= (3, 14):
    print(
        "Unsupported Python version for this project.\n"
        f"Detected: {sys.version}\n\n"
        "Please install Python 3.12 and run the app with that interpreter.\n"
        "Example (Windows):\n"
        "  py -3.12 -m venv venv\n"
        "  venv\\Scripts\\activate\n"
        "  pip install -r requirements.txt\n"
        "  python run.py"
    )
    raise SystemExit(1)

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Production: use a real WSGI server (gunicorn/uwsgi). This is dev-only.
    app.run(host="0.0.0.0", port=5000, debug=True)

