from datetime import timedelta

from app.extensions import bcrypt, db
from app.models import Capsule, User
from app.utils.time_utils import utcnow


def _create_user(app, email="user@example.com", password="password123"):
    with app.app_context():
        user = User(
            email=email.lower(),
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
            role="user",
        )
        db.session.add(user)
        db.session.commit()
        return user.id


def _create_capsule(app, user_id: int, title: str, message: str, unlock_at_utc):
    with app.app_context():
        capsule = Capsule(
            user_id=user_id,
            title=title,
            message=message,
            unlock_at_utc=unlock_at_utc,
        )
        db.session.add(capsule)
        db.session.commit()
        return capsule.id


def _login(client, email="user@example.com", password="password123"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def test_locked_capsule_cannot_be_opened(app, client):
    user_id = _create_user(app)
    locked_capsule_id = _create_capsule(
        app,
        user_id=user_id,
        title="Locked memory",
        message="This should never be accessible.",
        unlock_at_utc=utcnow() + timedelta(days=1),
    )

    _login(client)
    res = client.get(f"/capsules/{locked_capsule_id}/open")
    assert res.status_code == 403


def test_unlocked_capsule_can_be_opened_marks_opened(app, client):
    user_id = _create_user(app)
    unlocked_capsule_id = _create_capsule(
        app,
        user_id=user_id,
        title="Unlocked memory",
        message="Your future self says hi.",
        unlock_at_utc=utcnow() - timedelta(minutes=5),
    )

    _login(client)
    res = client.get(f"/capsules/{unlocked_capsule_id}/open")
    assert res.status_code == 200

    with app.app_context():
        refreshed = db.session.get(Capsule, unlocked_capsule_id)
        assert refreshed.opened_at_utc is not None

