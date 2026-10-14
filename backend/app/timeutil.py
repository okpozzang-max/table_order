"""시각 도구. 저장/응답은 UTC ISO 8601 문자열이고, 시각 공급원은 주입 가능한 clock이다."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

Clock = Callable[[], datetime]


def system_clock() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(dt: datetime) -> str:
    """UTC, 초 단위 ISO 8601 (`2026-10-14T05:00:00Z`)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
