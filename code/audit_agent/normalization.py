"""Conservative identifier and timestamp normalization."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from .errors import DataValidationError
from .models import IdentifierKind


def parse_timestamp(value: str, *, context: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise DataValidationError(f"{context}: invalid ISO-8601 timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise DataValidationError(f"{context}: timestamp must include a timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def normalize_email(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def normalize_phone(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip()
    prefix = "+" if value.startswith("+") else ""
    return prefix + re.sub(r"\D", "", value)


def normalize_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def normalize_identifier(kind: IdentifierKind, value: str) -> str:
    if kind == IdentifierKind.EMAIL:
        return normalize_email(value)
    if kind == IdentifierKind.PHONE:
        return normalize_phone(value)
    if kind == IdentifierKind.NAME:
        return normalize_name(value)
    return unicodedata.normalize("NFKC", value).strip().casefold()


def natural_id_key(value: str) -> tuple[str, int, str]:
    match = re.fullmatch(r"(.*?)(\d+)", value)
    return (match.group(1), int(match.group(2)), value) if match else (value, -1, value)
