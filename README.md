# Digital Time Capsule (Flask + SQLite)

A production-oriented Digital Time Capsule web app where users create locked capsules that remain inaccessible until their server-side unlock time.

## Features

- Secure authentication (registration/login/logout) with bcrypt + Flask-Login sessions
- Per-user capsule isolation
- Strict unlock enforcement on the backend (routes + file download/view endpoints return `403` while locked)
- Capsule categories:
  - `locked` (future unlock)
  - `unlocked` (unlock time reached, not yet opened)
  - `opened` (opened by the user at least once)
- Notifications generated automatically when capsules unlock (in-app notifications table; email optional via SMTP)
- Admin panel (role-based `admin` users):
  - View users and capsules
  - Suspend users
  - Delete capsules
- Optional capsule sharing links after unlock (unguessable token)

## Tech Stack

- Backend: Python + Flask
- ORM/DB: SQLAlchemy + SQLite (configurable)
- Auth: Flask-Login + Flask-Bcrypt
- Forms: Flask-WTF (CSRF protected)
- Scheduling: APScheduler (process-local polling for due unlock notifications)
- Frontend: Bootstrap + vanilla JS/CSS

## Setup (Step-by-step)

1. Install Python 3.12+
   - Your current run attempt used Python 3.14, which can break SQLAlchemy import.
   - Using Python 3.12 resolves this.
2. Open a terminal in this project folder
3. Install dependencies:
   - `pip install -r requirements.txt`
4. Set `SECRET_KEY` (recommended):
   - PowerShell: `setx SECRET_KEY "change-me-please"`
5. Initialize and seed sample data:
   - `python scripts/seed_db.py`
6. Run the app:
   - `python run.py`
7. Open in your browser:
   - `http://localhost:5000`

### If you see “unable to open database file”

- Usually `DATABASE_URL` points to a non-existent/unwritable folder.
- Fix by either:
  - Unset `DATABASE_URL` so the default project-local `instance/app.sqlite` is used, or
  - Set `DATABASE_URL` to a valid `sqlite:///...` path and ensure the parent folder exists.

### Sample Credentials (from seeding)

The seed script uses these defaults unless you override env vars:
- Admin: `admin@example.com` / `admin12345`
- User: `user@example.com` / `user12345`

## Environment Variables

- `SECRET_KEY` (required for production; defaults to `dev-change-me`)
- `DATABASE_URL` (default: absolute path to `instance/app.sqlite`)
- `UPLOAD_FOLDER` (default: absolute path to `instance/uploads`)
- `MAX_CONTENT_LENGTH` (default: `20` => 20MB)
- `NOTIFICATION_SCAN_INTERVAL_SECONDS` (default: `30`)
- Email (optional):
  - `ENABLE_EMAIL_NOTIFICATIONS=1`
  - `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`

## Database Schema

- `users`
  - `id`, `email`, `password_hash`, `role` (`user`/`admin`), `is_suspended`, `created_at_utc`
- `capsules`
  - `id`, `user_id`, `title`, `message`
  - `unlock_at_utc` (UTC time), `opened_at_utc` (nullable)
  - `created_at_utc`
- `capsule_files`
  - `id`, `capsule_id`, `file_category`, `original_filename`, `stored_filename`, `mime_type`, `size_bytes`
  - `created_at_utc`
- `capsule_share_tokens`
  - `id`, `capsule_id`, `token` (unguessable), `created_at_utc`, `expires_at_utc` (nullable)
- `notifications`
  - `id`, `user_id`, `capsule_id`, `kind`, `message`
  - `created_at_utc`, `read_at_utc`

## API Routes (locked content never returned)

- `GET /api/capsules`
  - Returns capsule metadata only: `id`, `title`, `status`, `unlock_at_utc`, `opened`
- `GET /api/capsules/<capsule_id>/open`
  - Returns full capsule content (`message` + file URLs) but only if unlocked

## Security Notes

- All unlock gating is enforced by the backend using server UTC time (`unlock_at_utc` vs current server time).
- Locked capsules return `403` for:
  - `/capsules/<id>/open`
  - `/capsules/<id>/file/<file_id>`
  - `/capsules/<id>/download/<file_id>`
- File storage uses server-generated names and per-capsule folders:
  - `instance/uploads/<user_id>/<capsule_id>/<stored_filename>`

## Tests

- Run: `pytest`
- Includes focused unlock-gating tests to prevent opening locked capsules.

