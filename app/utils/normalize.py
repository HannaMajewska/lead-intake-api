import re
from datetime import datetime, timezone


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().split())


def normalize_email(value: str | None) -> str:
    return clean_text(value).lower()


def normalize_phone(value: str | None) -> str:
    raw = clean_text(value)
    if not raw:
        return ""

    keep_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)

    if not digits:
        return ""

    return f"+{digits}" if keep_plus else digits


def normalize_slugish(value: str | None) -> str:
    cleaned = clean_text(value).lower()
    cleaned = cleaned.replace(" ", "_")
    cleaned = re.sub(r"[^a-z0-9_\-]", "", cleaned)
    return cleaned


def normalize_created_at(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)