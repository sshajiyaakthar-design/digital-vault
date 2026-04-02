import os
from datetime import timedelta

from app import create_app
from app.extensions import bcrypt, db
from app.models import Capsule, User
from app.utils.time_utils import utcnow


def main():
    app = create_app()

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin12345")
    user_email = os.environ.get("USER_EMAIL", "user@example.com").lower()
    user_password = os.environ.get("USER_PASSWORD", "user12345")

    with app.app_context():
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            admin = User(
                email=admin_email,
                password_hash=bcrypt.generate_password_hash(admin_password).decode("utf-8"),
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()
            print(f"Created admin: {admin_email}")
        else:
            print(f"Admin exists: {admin_email}")

        user = User.query.filter_by(email=user_email).first()
        if not user:
            user = User(
                email=user_email,
                password_hash=bcrypt.generate_password_hash(user_password).decode("utf-8"),
                role="user",
            )
            db.session.add(user)
            db.session.commit()
            print(f"Created user: {user_email}")
        else:
            print(f"User exists: {user_email}")

        # Locked capsule
        locked = Capsule.query.filter_by(user_id=user.id, title="Locked sample").first()
        if not locked:
            locked = Capsule(
                user_id=user.id,
                title="Locked sample",
                message="This capsule will unlock in the future.",
                unlock_at_utc=utcnow() + timedelta(days=1),
            )
            db.session.add(locked)

        # Unlocked but unopened
        unlocked = Capsule.query.filter_by(user_id=user.id, title="Unlocked sample").first()
        if not unlocked:
            unlocked = Capsule(
                user_id=user.id,
                title="Unlocked sample",
                message="This capsule unlocks immediately (but is not opened yet).",
                unlock_at_utc=utcnow() - timedelta(minutes=30),
            )
            db.session.add(unlocked)

        # Opened
        opened = Capsule.query.filter_by(user_id=user.id, title="Opened sample").first()
        if not opened:
            opened = Capsule(
                user_id=user.id,
                title="Opened sample",
                message="This capsule is already marked as opened.",
                unlock_at_utc=utcnow() - timedelta(days=2),
                opened_at_utc=utcnow() - timedelta(days=1),
            )
            db.session.add(opened)

        db.session.commit()
        print("Seed completed.")
        print("Sample credentials:")
        print(f"  Admin: {admin_email} / {admin_password}")
        print(f"  User:  {user_email} / {user_password}")


if __name__ == "__main__":
    main()

