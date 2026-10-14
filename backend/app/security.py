"""비밀번호 해시(bcrypt)와 토큰(JWT HS256).

만료 판정은 PyJWT 대신 주입된 clock으로 직접 수행한다 (테스트에서 시간 이동 가능).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import bcrypt
import jwt

from .errors import Unauthorized
from .timeutil import Clock

_MAX_BCRYPT_BYTES = 72
_ALGORITHM = "HS256"


def hash_password(plain: str, rounds: int = 12) -> str:
    data = plain.encode("utf-8")
    if len(data) > _MAX_BCRYPT_BYTES:
        raise ValueError("비밀번호가 너무 길어요 (최대 72바이트)")
    return bcrypt.hashpw(data, bcrypt.gensalt(rounds=rounds)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """일치 여부. 72바이트 초과 입력이나 잘못된 해시는 False."""
    data = plain.encode("utf-8")
    if len(data) > _MAX_BCRYPT_BYTES:
        return False
    try:
        return bcrypt.checkpw(data, hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class TokenClaims:
    sub: str
    role: str  # 'admin' | 'table'
    store_id: str
    iat: int
    exp: int
    table_id: int | None = None
    table_number: int | None = None


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_at: datetime


class TokenService:
    def __init__(self, *, secret: str, ttl_hours: int, store_id: str, clock: Clock) -> None:
        self._secret = secret
        self._ttl = timedelta(hours=ttl_hours)
        self._store_id = store_id
        self._clock = clock

    def _issue(self, claims: dict[str, object]) -> IssuedToken:
        now = self._clock()
        exp = now + self._ttl
        payload = {**claims, "storeId": self._store_id, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
        token = jwt.encode(payload, self._secret, algorithm=_ALGORITHM)
        return IssuedToken(token=token, expires_at=datetime.fromtimestamp(int(exp.timestamp()), tz=exp.tzinfo))

    def create_admin_token(self, username: str) -> IssuedToken:
        return self._issue({"sub": f"admin:{username}", "role": "admin"})

    def create_table_token(self, table_id: int, table_number: int) -> IssuedToken:
        return self._issue(
            {"sub": f"table:{table_id}", "role": "table", "tableId": table_id, "tableNumber": table_number}
        )

    def decode(self, token: str, *, expected_role: str) -> TokenClaims:
        """서명, 만료, role, storeId를 검증한다. 실패는 모두 Unauthorized."""
        try:
            data = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],
                options={"verify_exp": False, "verify_iat": False, "require": ["exp", "iat", "sub", "role"]},
            )
        except jwt.PyJWTError:
            raise Unauthorized() from None

        try:
            exp = int(data["exp"])
            iat = int(data["iat"])
            role = str(data["role"])
            sub = str(data["sub"])
            store_id = str(data.get("storeId", ""))
            table_id = int(data["tableId"]) if "tableId" in data else None
            table_number = int(data["tableNumber"]) if "tableNumber" in data else None
        except (TypeError, ValueError, KeyError):
            raise Unauthorized() from None

        if exp <= int(self._clock().timestamp()):
            raise Unauthorized()
        if role != expected_role or store_id != self._store_id:
            raise Unauthorized()
        if role == "table" and table_id is None:
            raise Unauthorized()
        return TokenClaims(
            sub=sub, role=role, store_id=store_id, iat=iat, exp=exp, table_id=table_id, table_number=table_number
        )
