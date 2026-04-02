from __future__ import annotations

from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from flask import Flask
from flask_mail import Message
from sqlalchemy.exc import IntegrityError

from ..models import Capsule, Notification, User
from ..utils.time_utils import utcnow
from ..extensions import mail, db


def _send_email_if_configured(app: Flask, user: User, capsule: Capsule):
    if not app.config.get("ENABLE_EMAIL_NOTIFICATIONS"):
        return

    # If mail server isn't configured, silently skip email notifications.
    if not app.config.get("MAIL_SERVER"):
        return

    with app.app_context():
        msg = Message(
            subject="Your Digital Time Capsule is unlocked",
            recipients=[user.email],
            body=f'Your capsule "{capsule.title}" has been unlocked.',
        )
        msg.sender = app.config.get("MAIL_DEFAULT_SENDER")
        mail.send(msg)


def scan_and_notify(app: Flask):
    now_utc = utcnow()
    # SQLite often stores datetime without tzinfo. Use a naive UTC datetime for SQL comparisons.
    now_for_db = now_utc.replace(tzinfo=None)
    with app.app_context():
        due = Capsule.query.filter(
            Capsule.unlock_at_utc <= now_for_db,
        ).all()

        for capsule in due:
            owner = capsule.owner
            if not owner or owner.is_suspended:
                continue

            message = f'Your capsule "{capsule.title}" is now unlocked.'
            notif = Notification(
                user_id=owner.id,
                capsule_id=capsule.id,
                kind="capsule_unlocked",
                message=message,
            )

            try:
                db.session.add(notif)
                db.session.commit()
            except IntegrityError:
                # Unique constraint de-dupes notifications.
                db.session.rollback()

            _send_email_if_configured(app, owner, capsule)


def start_notification_scheduler(app: Flask):
    scheduler = BackgroundScheduler(timezone="UTC")

    # Use daemon threads so the process can exit cleanly.
    scheduler.add_job(
        func=scan_and_notify,
        trigger=IntervalTrigger(seconds=app.config["NOTIFICATION_SCAN_INTERVAL_SECONDS"]),
        args=[app],
        id="capsule_unlock_scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    app.logger.info("Notification scheduler started.")

