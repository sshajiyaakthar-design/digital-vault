from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class UnlockInput:
    unlock_at_utc: datetime
    # For display only (not used for unlock gating)
    unlock_at_local: datetime


def parse_unlock_time(unlock_local_str: str, client_tz_offset_minutes: int | None) -> UnlockInput:
    """
    Convert a client-provided `datetime-local` string into a UTC datetime.

    `client_tz_offset_minutes` is expected to be the offset from UTC *in minutes* for the client time.
    Example: for UTC+2, offset = +120.
    """
    if not unlock_local_str:
        raise ValueError("Missing unlock time.")

    # datetime-local: "YYYY-MM-DDTHH:MM"
    try:
        local_naive = datetime.fromisoformat(unlock_local_str)
    except ValueError as e:
        raise ValueError("Invalid unlock time format.") from e

    if local_naive.tzinfo is not None:
        # Should not happen with datetime-local inputs, but keep it safe.
        local_naive = local_naive.replace(tzinfo=None)

    offset_minutes = client_tz_offset_minutes or 0
    unlock_local = local_naive.replace(tzinfo=timezone(timedelta(minutes=offset_minutes)))

    # Convert to UTC
    unlock_at_utc = unlock_local.astimezone(timezone.utc).replace(tzinfo=timezone.utc)
    return UnlockInput(unlock_at_utc=unlock_at_utc, unlock_at_local=unlock_at_utc)

