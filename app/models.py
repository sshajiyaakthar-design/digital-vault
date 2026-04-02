from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(db.String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)

    role: Mapped[str] = mapped_column(db.String(30), nullable=False, default="user")
    is_suspended: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)

    created_at_utc: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    capsules = relationship("Capsule", back_populates="owner", cascade="all, delete-orphan")
    notifications = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_active(self):
        # Flask-Login uses is_active; keep semantics explicit.
        return not self.is_suspended


class Capsule(db.Model):
    __tablename__ = "capsules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)

    title: Mapped[str] = mapped_column(db.String(200), nullable=False)
    message: Mapped[str] = mapped_column(db.Text, nullable=False, default="")

    unlock_at_utc: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False)
    opened_at_utc: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)

    created_at_utc: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    owner = relationship("User", back_populates="capsules")
    files = relationship("CapsuleFile", back_populates="capsule", cascade="all, delete-orphan")
    notifications = relationship(
        "Notification", back_populates="capsule", cascade="all, delete-orphan"
    )
    shares = relationship("CapsuleShareToken", back_populates="capsule", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("unlock_at_utc IS NOT NULL", name="capsule_unlock_at_not_null"),
    )

    @staticmethod
    def _as_utc_aware(dt: datetime | None) -> datetime | None:
        # SQLite typically stores datetime without timezone info, so tzinfo may be lost.
        # Normalize to UTC-aware datetimes for safe comparisons in Python.
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def status(self, now_utc: datetime | None = None) -> str:
        if now_utc is None:
            now_utc = utcnow()
        now_utc = self._as_utc_aware(now_utc)  # type: ignore[assignment]

        unlock_at = self._as_utc_aware(self.unlock_at_utc)
        if unlock_at is None:
            # Should never happen due to DB constraint.
            return "locked"

        if self.opened_at_utc is not None:
            return "opened"
        if unlock_at <= now_utc:
            return "unlocked"
        return "locked"


class CapsuleFile(db.Model):
    __tablename__ = "capsule_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    capsule_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("capsules.id"), index=True, nullable=False)

    file_category: Mapped[str] = mapped_column(db.String(20), nullable=False)  # image/audio/video/document
    original_filename: Mapped[str] = mapped_column(db.String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(db.String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(db.String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(db.Integer, nullable=False)

    created_at_utc: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    capsule = relationship("Capsule", back_populates="files")


class CapsuleShareToken(db.Model):
    __tablename__ = "capsule_share_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    capsule_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("capsules.id"), index=True, nullable=False)

    token: Mapped[str] = mapped_column(db.String(64), unique=True, index=True, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )
    expires_at_utc: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)

    capsule = relationship("Capsule", back_populates="shares")


class Notification(db.Model):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)
    capsule_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("capsules.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(db.String(30), nullable=False)  # e.g. capsule_unlocked

    message: Mapped[str] = mapped_column(db.Text, nullable=False)

    created_at_utc: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )
    read_at_utc: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="notifications")
    capsule = relationship("Capsule", back_populates="notifications")

    __table_args__ = (
        UniqueConstraint("user_id", "capsule_id", "kind", name="uq_notification_dedupe"),
    )

