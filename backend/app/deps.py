"""앱 컨테이너와 인증 의존성."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings
from .db import Database
from .errors import Unauthorized
from .events import EventBroker
from .security import TokenService
from .services.auth_service import AuthService
from .services.menu_service import MenuService
from .services.order_service import OrderService
from .services.table_service import TableService
from .timeutil import Clock


@dataclass
class AppContainer:
    settings: Settings
    db: Database
    clock: Clock
    tokens: TokenService
    auth: AuthService
    menus: MenuService
    tables: TableService
    orders: OrderService
    broker: EventBroker


@dataclass(frozen=True)
class AdminPrincipal:
    username: str
    expires_at: int | None = None  # 토큰 exp (epoch 초). SSE가 만료 시 스트림을 닫는 데 사용


@dataclass(frozen=True)
class TablePrincipal:
    table_id: int
    table_number: int


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


# 계약의 보안 스킴 이름과 맞춘다 (OpenAPI securitySchemes).
admin_scheme = HTTPBearer(auto_error=False, scheme_name="adminBearer", description="관리자 로그인으로 발급된 JWT")
table_scheme = HTTPBearer(auto_error=False, scheme_name="tableBearer", description="테이블 로그인으로 발급된 JWT")


def require_admin(
    container: AppContainer = Depends(get_container),
    creds: HTTPAuthorizationCredentials | None = Depends(admin_scheme),
) -> AdminPrincipal:
    if creds is None or not creds.credentials:
        raise Unauthorized()
    claims = container.tokens.decode(creds.credentials, expected_role="admin")
    return AdminPrincipal(username=claims.sub.removeprefix("admin:"), expires_at=claims.exp)


def require_table(
    container: AppContainer = Depends(get_container),
    creds: HTTPAuthorizationCredentials | None = Depends(table_scheme),
) -> TablePrincipal:
    if creds is None or not creds.credentials:
        raise Unauthorized()
    claims = container.tokens.decode(creds.credentials, expected_role="table")
    assert claims.table_id is not None
    with container.db.connection() as conn:
        row = conn.execute("SELECT id, table_number FROM tables WHERE id = ?", (claims.table_id,)).fetchone()
    if row is None:  # 삭제/재설정된 테이블의 토큰
        raise Unauthorized()
    return TablePrincipal(table_id=row["id"], table_number=row["table_number"])
