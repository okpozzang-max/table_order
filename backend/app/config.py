"""설정 로드와 검증. 값 자체는 오류 메시지에 노출하지 않는다 (키 이름만)."""

from __future__ import annotations

import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent

DEFAULT_DB_PATH = _BACKEND_DIR / "data" / "table_order.sqlite3"
DEFAULT_FRONTEND_DIST = _REPO_ROOT / "frontend" / "dist"

_BCRYPT_HASH = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")


class ConfigError(Exception):
    """설정 오류. 어떤 키가 문제인지만 알린다."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    store_id: str = Field(min_length=1, max_length=50)
    admin_username: str = Field(min_length=1, max_length=100)
    admin_password_hash: str
    jwt_secret: str = Field(min_length=32)
    db_path: Path = DEFAULT_DB_PATH
    token_ttl_hours: int = Field(default=16, ge=1)
    admin_login_max_failures: int = Field(default=5, ge=1)
    admin_login_lock_minutes: int = Field(default=15, ge=1)
    table_login_max_failures: int = Field(default=10, ge=1)
    table_login_lock_minutes: int = Field(default=5, ge=1)
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)
    frontend_dist: Path = DEFAULT_FRONTEND_DIST
    timezone: str = "Asia/Seoul"
    sse_keepalive_seconds: int = Field(default=15, ge=1)
    sse_queue_size: int = Field(default=100, ge=1)

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, v: str) -> str:
        v = v.strip()
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            raise ValueError("unknown timezone") from None
        return v

    @field_validator("store_id", "admin_username")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("empty")
        return v

    @field_validator("admin_password_hash")
    @classmethod
    def _bcrypt_format(cls, v: str) -> str:
        if not _BCRYPT_HASH.match(v):
            raise ValueError("not a bcrypt hash")
        return v


def load_settings() -> Settings:
    """환경 변수/.env에서 설정을 읽는다. 문제가 있으면 키 이름만 담은 ConfigError."""
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        keys = sorted({str(err["loc"][0]).upper() for err in exc.errors() if err.get("loc")})
        raise ConfigError(
            "설정 오류: 다음 항목을 확인해주세요 -> " + ", ".join(keys) + " (backend/.env.example 참고)"
        ) from None
