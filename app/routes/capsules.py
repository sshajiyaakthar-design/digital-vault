import os
from datetime import datetime

import io
import zipfile

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..forms import CapsuleCreateForm
from ..models import Capsule, CapsuleFile
from ..utils.storage import capsule_storage_dir, make_stored_filename, safe_original_filename, validate_upload
from ..utils.time_utils import parse_unlock_time, utcnow

bp = Blueprint("capsules", __name__)


def _now_utc():
    return utcnow()


def _get_owned_capsule_or_404(capsule_id: int) -> Capsule:
    capsule = Capsule.query.filter_by(id=capsule_id, user_id=current_user.id).first()
    if not capsule:
        abort(404)
    return capsule


def _assert_unlocked_for_owned(capsule: Capsule):
    now = _now_utc()
    if capsule.status(now) == "locked":
        abort(403)


@bp.route("/dashboard")
@login_required
def dashboard():
    status_filter = request.args.get("status", "all")
    q_term = (request.args.get("q") or "").strip()
    now = _now_utc()

    q = Capsule.query.filter_by(user_id=current_user.id)
    if q_term:
        q = q.filter(Capsule.title.ilike(f"%{q_term}%"))

    capsules = q.order_by(Capsule.created_at_utc.desc()).all()

    def compute_status(c: Capsule) -> str:
        return c.status(now)

    filtered = []
    for c in capsules:
        st = compute_status(c)
        if status_filter == "all" or st == status_filter:
            filtered.append((c, st))

    return render_template("dashboard.html", capsules=filtered, status_filter=status_filter, now_utc=now)


@bp.route("/capsules/new", methods=["GET", "POST"])
@login_required
def create_capsule():
    form = CapsuleCreateForm()
    if form.validate_on_submit():
        title = form.title.data.strip()
        message = (form.message.data or "").strip()

        unlock_local_str = form.unlock_local.data
        try:
            client_offset_raw = form.client_tz_offset_minutes.data
            client_offset = int(client_offset_raw) if client_offset_raw not in (None, "") else None
        except ValueError:
            client_offset = None

        try:
            unlock_input = parse_unlock_time(unlock_local_str, client_offset)
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("create_capsule.html", form=form)

        now = _now_utc()
        if unlock_input.unlock_at_utc <= now:
            flash("Unlock time must be in the future (server time).", "warning")
            return render_template("create_capsule.html", form=form)

        capsule = Capsule(
            user_id=current_user.id,
            title=title,
            message=message,
            unlock_at_utc=unlock_input.unlock_at_utc,
        )
        db.session.add(capsule)
        db.session.commit()

        # Handle uploads (multiple files under the same input name: "files")
        uploaded_files = request.files.getlist("files")
        if uploaded_files:
            for f in uploaded_files:
                if not f or not f.filename:
                    continue

                try:
                    category, ext, mime_type, size_bytes = validate_upload(f, current_app.config)
                    stored_filename = make_stored_filename(ext)
                    original_safe = safe_original_filename(f.filename)

                    storage_dir = capsule_storage_dir(current_app.config["UPLOAD_FOLDER"], current_user.id, capsule.id)
                    os.makedirs(storage_dir, exist_ok=True)
                    target_path = os.path.join(storage_dir, stored_filename)

                    # Persist file to disk
                    f.save(target_path)

                    cf = CapsuleFile(
                        capsule_id=capsule.id,
                        file_category=category,
                        original_filename=original_safe,
                        stored_filename=stored_filename,
                        mime_type=mime_type,
                        size_bytes=size_bytes,
                    )
                    db.session.add(cf)
                    db.session.commit()
                except ValueError as e:
                    flash(f"Upload skipped: {e}", "warning")
                except SQLAlchemyError:
                    db.session.rollback()
                    flash("File upload failed. Try again.", "danger")
                except Exception:
                    db.session.rollback()
                    flash("File upload failed. Try again.", "danger")

        flash("Capsule created. It will unlock automatically.", "success")
        return redirect(url_for("capsules.dashboard"))

    return render_template("create_capsule.html", form=form)


@bp.route("/capsules/<int:capsule_id>/open")
@login_required
def open_capsule(capsule_id: int):
    capsule = _get_owned_capsule_or_404(capsule_id)
    _assert_unlocked_for_owned(capsule)

    # Mark as opened for the user.
    if capsule.opened_at_utc is None:
        capsule.opened_at_utc = _now_utc()
        db.session.add(capsule)
        db.session.commit()

    files = sorted(capsule.files, key=lambda f: f.created_at_utc or datetime.min)
    return render_template("open_capsule.html", capsule=capsule, files=files, now_utc=_now_utc())


@bp.route("/capsules/<int:capsule_id>/file/<int:file_id>")
@login_required
def capsule_file(capsule_id: int, file_id: int):
    capsule = _get_owned_capsule_or_404(capsule_id)
    _assert_unlocked_for_owned(capsule)

    cf = CapsuleFile.query.filter_by(id=file_id, capsule_id=capsule.id).first()
    if not cf:
        abort(404)

    storage_dir = capsule_storage_dir(current_app.config["UPLOAD_FOLDER"], current_user.id, capsule.id)
    target_path = os.path.join(storage_dir, cf.stored_filename)
    if not os.path.exists(target_path):
        abort(404)

    # send_file avoids exposing filesystem paths.
    return send_file(target_path, mimetype=cf.mime_type, as_attachment=False, download_name=cf.original_filename)


@bp.route("/capsules/<int:capsule_id>/download/<int:file_id>")
@login_required
def download_capsule_file(capsule_id: int, file_id: int):
    capsule = _get_owned_capsule_or_404(capsule_id)
    _assert_unlocked_for_owned(capsule)

    cf = CapsuleFile.query.filter_by(id=file_id, capsule_id=capsule.id).first()
    if not cf:
        abort(404)

    storage_dir = capsule_storage_dir(current_app.config["UPLOAD_FOLDER"], current_user.id, capsule.id)
    target_path = os.path.join(storage_dir, cf.stored_filename)
    if not os.path.exists(target_path):
        abort(404)

    return send_file(target_path, mimetype=cf.mime_type, as_attachment=True, download_name=cf.original_filename)


@bp.route("/capsules/<int:capsule_id>/download-all")
@login_required
def download_all_capsule_content(capsule_id: int):
    capsule = _get_owned_capsule_or_404(capsule_id)
    _assert_unlocked_for_owned(capsule)

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("message.txt", capsule.message or "")
        for cf in capsule.files:
            storage_dir = capsule_storage_dir(
                current_app.config["UPLOAD_FOLDER"], current_user.id, capsule.id
            )
            target_path = os.path.join(storage_dir, cf.stored_filename)
            if os.path.exists(target_path):
                zf.write(target_path, arcname=cf.original_filename)

    mem.seek(0)
    return send_file(
        mem,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"capsule_{capsule.id}.zip",
    )


@bp.route("/api/capsules")
@login_required
def api_capsules():
    # Metadata only. Locked capsule content is never returned.
    now = _now_utc()
    capsules = Capsule.query.filter_by(user_id=current_user.id).order_by(Capsule.created_at_utc.desc()).all()

    data = []
    for c in capsules:
        st = c.status(now)
        data.append(
            {
                "id": c.id,
                "title": c.title,
                "status": st,
                "unlock_at_utc": c.unlock_at_utc.isoformat(),
                "opened": c.opened_at_utc is not None,
            }
        )
    return {"capsules": data}


@bp.route("/api/capsules/<int:capsule_id>/open")
@login_required
def api_open_capsule(capsule_id: int):
    capsule = _get_owned_capsule_or_404(capsule_id)
    _assert_unlocked_for_owned(capsule)

    # Mark opened (server-side).
    if capsule.opened_at_utc is None:
        capsule.opened_at_utc = _now_utc()
        db.session.add(capsule)
        db.session.commit()

    files = [
        {
            "id": f.id,
            "category": f.file_category,
            "original_filename": f.original_filename,
            "download_url": url_for("capsules.download_capsule_file", capsule_id=capsule.id, file_id=f.id, _external=True),
            "view_url": url_for("capsules.capsule_file", capsule_id=capsule.id, file_id=f.id, _external=True),
        }
        for f in capsule.files
    ]
    return {
        "id": capsule.id,
        "title": capsule.title,
        "message": capsule.message,
        "unlock_at_utc": capsule.unlock_at_utc.isoformat(),
        "opened_at_utc": capsule.opened_at_utc.isoformat() if capsule.opened_at_utc else None,
        "files": files,
    }

