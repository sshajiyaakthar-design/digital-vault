from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Notification
from ..utils.time_utils import utcnow

bp = Blueprint("notifications", __name__)


@bp.route("/notifications")
@login_required
def notifications_list():
    # Mark as read on view.
    unread = Notification.query.filter_by(user_id=current_user.id, read_at_utc=None).all()
    if unread:
        now = utcnow()
        for n in unread:
            n.read_at_utc = now
        db.session.add_all(unread)
        db.session.commit()

    notifications = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at_utc.desc())
        .limit(50)
        .all()
    )
    return render_template("notifications.html", notifications=notifications)

