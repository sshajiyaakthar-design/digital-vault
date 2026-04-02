from flask import Blueprint, render_template
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Notification

bp = Blueprint("profile", __name__)


@bp.route("/profile")
@login_required
def profile_page():
    notifications = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at_utc.desc())
        .limit(50)
        .all()
    )

    # Do not auto-mark notifications as read; inbox should show real state.
    unread_count = sum(1 for n in notifications if n.read_at_utc is None)
    return render_template("profile.html", unread_count=unread_count, notifications=notifications)

