from datetime import timedelta

from app.extensions import db
from app.models import Capsule, Notification, User
from app.services.notifications import scan_and_notify
from app.utils.time_utils import utcnow


def test_unlock_notification_created_even_if_already_opened(app):
    user = User(
        email="n1@example.com",
        password_hash=app.config.get("SECRET_KEY", "x"),  # placeholder overwritten below
        role="user",
    )
    # bcrypt hash needs app.bcrypt; easiest: create via model helper route not available here.
    # We'll just use an already-hashed password by using db directly and skipping auth checks.
    # Password hash is not used by scan_and_notify.
    user.password_hash = "placeholder"

    with app.app_context():
        db.session.add(user)
        db.session.commit()

        capsule = Capsule(
            user_id=user.id,
            title="Already opened unlocked capsule",
            message="",
            unlock_at_utc=utcnow() - timedelta(minutes=5),
            opened_at_utc=utcnow() - timedelta(minutes=1),
        )
        db.session.add(capsule)
        db.session.commit()

        scan_and_notify(app)

        notif = Notification.query.filter_by(
            user_id=user.id, capsule_id=capsule.id, kind="capsule_unlocked"
        ).first()
        assert notif is not None

