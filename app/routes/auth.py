from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from ..extensions import bcrypt, db
from ..forms import LoginForm, RegisterForm
from ..models import User

bp = Blueprint("auth", __name__)


@bp.route("/")
def root_redirect():
    if current_user.is_authenticated:
        return redirect(url_for("capsules.dashboard"))
    return redirect(url_for("auth.landing"))


@bp.route("/landing")
def landing():
    return render_template("landing.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("capsules.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            flash("Please enter a valid email address.", "warning")
            return render_template("register.html", form=form)
        password = form.password.data

        user = User(email=email, password_hash=bcrypt.generate_password_hash(password).decode("utf-8"))

        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That email is already registered.", "warning")
            return render_template("register.html", form=form)

        login_user(user)
        flash("Welcome! Your account is ready.", "success")
        return redirect(url_for("capsules.dashboard"))

    return render_template("register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("capsules.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            flash("Invalid email or password.", "danger")
            return render_template("login.html", form=form)
        user = User.query.filter_by(email=email).first()
        if not user or not bcrypt.check_password_hash(user.password_hash, form.password.data):
            flash("Invalid email or password.", "danger")
            return render_template("login.html", form=form)

        if user.is_suspended:
            flash("Your account is suspended. Contact admin.", "danger")
            return render_template("login.html", form=form)

        login_user(user)
        flash("Logged in successfully.", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("capsules.dashboard"))

    return render_template("login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))

