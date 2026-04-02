import os
import secrets
from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, send_file, url_for, current_app
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Capsule, CapsuleFile, CapsuleShareToken
from ..utils.storage import capsule_storage_dir
from ..utils.time_utils import utcnow

bp = Blueprint("share", __name__)


def _assert_capsule_unlocked(capsule: Capsule):
    # Use model status() to safely compare naive/aware datetimes.
    if capsule.status(utcnow()) == "locked":
        abort(403)


def _assert_share_token_valid(st: CapsuleShareToken):
    # If we later add expiry, enforce it here.
    expires = st.expires_at_utc
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    now = utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if expires is not None and expires <= now:
        abort(404)


@bp.route("/capsules/<int:capsule_id>/create-share", methods=["POST"])
@login_required
def create_share(capsule_id: int):
    capsule = Capsule.query.filter_by(id=capsule_id, user_id=current_user.id).first_or_404()
    _assert_capsule_unlocked(capsule)

    # Optional: cap number of active share tokens per capsule if desired.
    token = secrets.token_urlsafe(32)
    st = CapsuleShareToken(capsule_id=capsule.id, token=token)
    db.session.add(st)
    db.session.commit()

    share_url = url_for("share.shared_capsule", token=token, _external=True)
    flash("Share link created. Keep it safe.", "success")
    flash(f"Share URL: {share_url}", "info")
    return redirect(url_for("capsules.open_capsule", capsule_id=capsule.id))


@bp.route("/share/<token>")
def shared_capsule(token: str):
    st = CapsuleShareToken.query.filter_by(token=token).first()
    if not st:
        abort(404)
    _assert_share_token_valid(st)

    capsule = st.capsule
    if not capsule:
        abort(404)

    _assert_capsule_unlocked(capsule)

    files = sorted(
        capsule.files,
        key=lambda f: f.created_at_utc or datetime.min.replace(tzinfo=timezone.utc),
    )
    return render_template("shared_capsule.html", token=token, capsule=capsule, files=files, now_utc=utcnow())


@bp.route("/share/<token>/file/<int:file_id>")
def shared_capsule_file(token: str, file_id: int):
    st = CapsuleShareToken.query.filter_by(token=token).first()
    if not st:
        abort(404)
    _assert_share_token_valid(st)

    capsule = st.capsule
    if not capsule:
        abort(404)

    _assert_capsule_unlocked(capsule)

    cf = CapsuleFile.query.filter_by(id=file_id, capsule_id=capsule.id).first()
    if not cf:
        abort(404)

    storage_dir = capsule_storage_dir(
        current_app.config["UPLOAD_FOLDER"],
        capsule.user_id,
        capsule.id,
    )
    target_path = os.path.join(storage_dir, cf.stored_filename)
    if not (target_path and os.path.exists(target_path)):
        abort(404)

    return send_file(target_path, mimetype=cf.mime_type, as_attachment=False, download_name=cf.original_filename)


@bp.route("/share/<token>/download/<int:file_id>")
def shared_capsule_download(token: str, file_id: int):
    st = CapsuleShareToken.query.filter_by(token=token).first()
    if not st:
        abort(404)
    _assert_share_token_valid(st)

    capsule = st.capsule
    if not capsule:
        abort(404)

    _assert_capsule_unlocked(capsule)

    cf = CapsuleFile.query.filter_by(id=file_id, capsule_id=capsule.id).first()
    if not cf:
        abort(404)

    storage_dir = capsule_storage_dir(
        current_app.config["UPLOAD_FOLDER"],
        capsule.user_id,
        capsule.id,
    )
    target_path = os.path.join(storage_dir, cf.stored_filename)
    if not (target_path and os.path.exists(target_path)):
        abort(404)

    return send_file(
        target_path,
        mimetype=cf.mime_type,
        as_attachment=True,
        download_name=cf.original_filename,
    )

