from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.deps import AppContainer
from app.events_port import ServerEvent
from app.main import build_container, create_app
from app.security import hash_password
from scripts.seed import run_seed

ADMIN_PASSWORD = "admin1234"
STORE_ID = "demo"
ADMIN_USERNAME = "admin"
TABLE_PASSWORD = "1234"


class FakeClock:
    """테스트용 시계. advance()로 시간을 이동한다."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 14, 0, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[ServerEvent] = []

    def publish(self, event: ServerEvent) -> None:
        self.events.append(event)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture(scope="session")
def admin_hash() -> str:
    return hash_password(ADMIN_PASSWORD, 4)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return tmp_path / "dist"


@pytest.fixture
def settings(tmp_path: Path, admin_hash: str, dist_dir: Path) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        store_id=STORE_ID,
        admin_username=ADMIN_USERNAME,
        admin_password_hash=admin_hash,
        jwt_secret="test-secret-" + "x" * 32,
        db_path=tmp_path / "test.sqlite3",
        bcrypt_rounds=4,
        frontend_dist=dist_dir,
    )


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def container(settings: Settings, clock: FakeClock, publisher: RecordingPublisher) -> AppContainer:
    return build_container(settings, clock, publisher)


@pytest.fixture
def seeded(container: AppContainer, clock: FakeClock) -> AppContainer:
    run_seed(container.db, bcrypt_rounds=4, now=clock())
    return container


@pytest.fixture
def app(settings: Settings, clock: FakeClock, publisher: RecordingPublisher):  # type: ignore[no-untyped-def]
    application = create_app(settings, clock, publisher)
    run_seed(application.state.container.db, bcrypt_rounds=4, now=clock())
    return application


@pytest.fixture
def client(app) -> TestClient:  # type: ignore[no-untyped-def]
    # 처리되지 않은 예외를 500 응답으로 확인할 수 있도록 서버 예외를 다시 던지지 않는다
    return TestClient(app, raise_server_exceptions=False)


def login_admin(client: TestClient) -> str:
    res = client.post(
        "/api/admin/auth/login",
        json={"storeId": STORE_ID, "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert res.status_code == 200, res.text
    return res.json()["accessToken"]


def login_table(client: TestClient, table_number: int = 1) -> str:
    res = client.post(
        "/api/customer/auth/login",
        json={"storeId": STORE_ID, "tableNumber": table_number, "password": TABLE_PASSWORD},
    )
    assert res.status_code == 200, res.text
    return res.json()["accessToken"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    return bearer(login_admin(client))


@pytest.fixture
def table_headers(client: TestClient) -> dict[str, str]:
    return bearer(login_table(client))


@pytest.fixture
def live(settings: Settings, clock: FakeClock, publisher: RecordingPublisher):  # type: ignore[no-untyped-def]
    """실제 uvicorn 서버(스레드)와 HTTP 헬퍼. keep-alive는 테스트용으로 1초."""
    from tests.live import Live, LiveServer  # 지연 import: tests.live 가 이 파일의 상수를 import 한다

    fast = settings.model_copy(update={"sse_keepalive_seconds": 1})
    application = create_app(fast, clock, publisher)
    container: AppContainer = application.state.container
    run_seed(container.db, bcrypt_rounds=4, now=clock())
    with LiveServer(application) as server:
        yield Live(server, container)
