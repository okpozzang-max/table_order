"""앱 조립: 설정/DB/서비스 구성, 라우터, 오류 핸들러, 정적 서빙(SPA 폴백).

실행: `python -m uvicorn app.main:create_app --factory --port 8000` (backend 디렉토리에서)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import schema_core  # noqa: F401  (core 스키마 모듈 등록)
from . import schema_order  # noqa: F401  (order 스키마 모듈 등록: core 다음)
from .config import Settings, load_settings
from .db import Database, init_schema
from .deps import AppContainer
from .errors import AppError, NotFound, Unauthorized, error_body, fields_from_request_errors
from .events import CompositePublisher, EventBroker
from .events_port import EventPublisher
from .routers import admin as admin_router
from .routers import admin_orders as admin_orders_router
from .routers import admin_tables as admin_tables_router
from .routers import customer as customer_router
from .routers import customer_orders as customer_orders_router
from .security import TokenService
from .services.auth_service import AuthService
from .services.menu_service import MenuService
from .services.order_service import OrderService
from .services.table_service import TableService
from .timeutil import Clock, system_clock

logger = logging.getLogger("app")


def build_container(
    settings: Settings, clock: Clock | None = None, event_publisher: EventPublisher | None = None
) -> AppContainer:
    """서비스를 조립한다. 이벤트는 항상 EventBroker(SSE)로 가고, event_publisher가 있으면 함께 전달된다(테스트용 기록 등)."""
    clock = clock or system_clock
    db = Database(settings.db_path)
    init_schema(db)
    tokens = TokenService(
        secret=settings.jwt_secret, ttl_hours=settings.token_ttl_hours, store_id=settings.store_id, clock=clock
    )
    broker = EventBroker(queue_size=settings.sse_queue_size)
    publisher: EventPublisher = CompositePublisher(broker, event_publisher) if event_publisher else broker
    menus = MenuService(db=db, clock=clock, publisher=publisher)  # menu_changed 발행
    tables = TableService(
        db=db, clock=clock, bcrypt_rounds=settings.bcrypt_rounds, timezone=settings.timezone, publisher=publisher
    )
    return AppContainer(
        settings=settings,
        db=db,
        clock=clock,
        tokens=tokens,
        auth=AuthService(settings=settings, db=db, tokens=tokens, clock=clock),
        menus=menus,
        tables=tables,
        orders=OrderService(db=db, clock=clock, menus=menus, tables=tables, publisher=publisher),
        broker=broker,
    )


def create_app(
    settings: Settings | None = None,
    clock: Clock | None = None,
    event_publisher: EventPublisher | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    container = build_container(settings, clock, event_publisher)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        container.broker.close_all()  # 서버 종료 시 열린 SSE 스트림을 닫는다

    app = FastAPI(
        title="Table Order API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.container = container

    _register_error_handlers(app)
    app.include_router(customer_router.router)
    app.include_router(customer_orders_router.router)
    app.include_router(admin_router.router)
    app.include_router(admin_orders_router.router)
    app.include_router(admin_tables_router.router)
    _register_static(app, settings.frontend_dist)
    return app


def _json_error(exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_body(), headers=exc.headers)


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        return _json_error(exc)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = fields_from_request_errors([dict(e) for e in exc.errors()])
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "입력한 내용을 확인해주세요.", fields=fields),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code in (404, 405):
            return _json_error(NotFound()) if exc.status_code == 404 else JSONResponse(
                status_code=405, content=error_body("NOT_FOUND", "대상을 찾을 수 없어요.")
            )
        if exc.status_code == 401:
            return _json_error(Unauthorized())
        return JSONResponse(
            status_code=exc.status_code, content=error_body("INTERNAL_ERROR", "요청을 처리하지 못했어요.")
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        # 내부 정보는 응답에 싣지 않고 서버 로그에만 남긴다
        logger.error("처리되지 않은 예외", exc_info=exc)
        return JSONResponse(
            status_code=500, content=error_body("INTERNAL_ERROR", "문제가 발생했어요. 잠시 후 다시 시도해주세요.")
        )


def _register_static(app: FastAPI, dist: Path) -> None:
    """프론트엔드 빌드 산출물 정적 서빙 + SPA 폴백. /api/* 는 폴백 대상이 아니다(JSON 404)."""
    index = dist / "index.html"
    serving = index.is_file()
    if serving:
        logger.info("프론트엔드 정적 파일을 서빙합니다: %s", dist)
    else:
        logger.warning("프론트엔드 빌드(%s)가 없어 API만 제공합니다. `npm run build` 후 다시 시작하세요.", dist)
    root = dist.resolve()

    @app.api_route(
        "/{full_path:path}",
        methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        include_in_schema=False,
    )
    def _spa(full_path: str, request: Request) -> Response:
        if full_path == "api" or full_path.startswith("api/") or not serving or request.method not in ("GET", "HEAD"):
            raise NotFound()
        candidate = (root / full_path).resolve()
        if candidate != root and root in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)
