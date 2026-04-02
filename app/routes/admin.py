import os

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user, login_required, login_user
from sqlalchemy import func

from ..extensions import bcrypt, db
from ..forms import LoginForm
from ..models import Capsule, User
from ..utils.storage import capsule_storage_dir
from ..utils.time_utils import utcnow

bp = Blueprint("admin", __name__)


def _require_admin():
    if not current_user.is_authenticated:
        abort(401)
    if getattr(current_user, "role", None) != "admin" or current_user.is_suspended:
        abort(403)


@bp.route("/login", methods=["GET", "POST"])
def login_admin():
    if current_user.is_authenticated and getattr(current_user, "role", None) == "admin":
        return redirect(url_for("admin.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if (
            not user
            or user.role != "admin"
            or user.is_suspended
            or not bcrypt.check_password_hash(user.password_hash, form.password.data)
        ):
            flash("Invalid admin credentials.", "danger")
            return render_template("admin_login.html", form=form)

        login_user(user)
        flash("Admin login successful.", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("admin.dashboard"))

    return render_template("admin_login.html", form=form)


@bp.route("/")
@login_required
def dashboard():
    _require_admin()
    now = utcnow()

    total_users = db.session.query(func.count(User.id)).scalar() or 0
    total_capsules = db.session.query(func.count(Capsule.id)).scalar() or 0

    locked_count = 0
    unlocked_count = 0
    opened_count = 0

    capsules = Capsule.query.order_by(Capsule.created_at_utc.desc()).all()
    for c in capsules:
        st = c.status(now)
        if st == "locked":
            locked_count += 1
        elif st == "unlocked":
            unlocked_count += 1
        else:
            opened_count += 1

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_capsules=total_capsules,
        locked_count=locked_count,
        unlocked_count=unlocked_count,
        opened_count=opened_count,
    )


@bp.route("/users")
@login_required
def users():
    _require_admin()
    users_list = User.query.order_by(User.created_at_utc.desc()).all()
    return render_template("admin_users.html", users_list=users_list)


@bp.route("/users/<int:user_id>/toggle-suspension", methods=["POST"])
@login_required
def toggle_suspension(user_id: int):
    _require_admin()
    if user_id == current_user.id:
        flash("You cannot suspend yourself.", "warning")
        return redirect(url_for("admin.users"))

    user = User.query.get_or_404(user_id)
    user.is_suspended = not user.is_suspended
    db.session.add(user)
    db.session.commit()
    flash("User status updated.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/capsules")
@login_required
def capsules():
    _require_admin()
    now = utcnow()
    capsules_list = Capsule.query.order_by(Capsule.created_at_utc.desc()).all()
    enriched = []
    for c in capsules_list:
        enriched.append(
            {
                "capsule": c,
                "status": c.status(now),
                "owner_email": c.owner.email if c.owner else None,
            }
        )
    return render_template("admin_capsules.html", enriched=enriched)


@bp.route("/capsules/<int:capsule_id>/delete", methods=["POST"])
@login_required
def delete_capsule(capsule_id: int):
    _require_admin()
    capsule = Capsule.query.get_or_404(capsule_id)

    # Delete stored files on disk.
    for f in capsule.files:
        storage_dir = capsule_storage_dir(
            current_app.config["UPLOAD_FOLDER"], capsule.user_id, capsule.id
        )
        target_path = os.path.join(storage_dir, f.stored_filename)
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass

    # Remove the record (DB cascades delete files/tokens/notifications).
    db.session.delete(capsule)
    db.session.commit()
    flash("Capsule deleted.", "success")
    return redirect(url_for("admin.capsules"))

