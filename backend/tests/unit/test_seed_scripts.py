from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.db import Database, registered_modules
from app.security import verify_password
from scripts import seed
from scripts.seed import SEED_MENUS, SEED_TABLE_NUMBERS, SEED_TABLE_PASSWORD, reset_data, run_seed

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _counts(db: Database) -> tuple[int, int]:
    with db.connection() as conn:
        return (
            conn.execute("SELECT COUNT(*) AS n FROM tables").fetchone()["n"],
            conn.execute("SELECT COUNT(*) AS n FROM menus").fetchone()["n"],
        )


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "seed.sqlite3")


def test_seed_inserts_tables_and_menus(db: Database) -> None:
    assert run_seed(db, bcrypt_rounds=4) == "seeded"
    assert _counts(db) == (len(SEED_TABLE_NUMBERS), len(SEED_MENUS))
    with db.connection() as conn:
        hashes = [r["password_hash"] for r in conn.execute("SELECT password_hash FROM tables")]
        cats = [r["category"] for r in conn.execute("SELECT DISTINCT category FROM menus ORDER BY category_order")]
    assert all(verify_password(SEED_TABLE_PASSWORD, h) for h in hashes)
    assert cats == ["메인", "사이드", "음료", "디저트"]


def test_seed_is_idempotent(db: Database) -> None:
    run_seed(db, bcrypt_rounds=4)
    assert run_seed(db, bcrypt_rounds=4) == "skipped"
    assert _counts(db) == (len(SEED_TABLE_NUMBERS), len(SEED_MENUS))


def test_seed_skips_if_only_menus_exist(db: Database) -> None:
    run_seed(db, bcrypt_rounds=4)
    with db.transaction() as conn:
        conn.execute("DELETE FROM tables")
    assert run_seed(db, bcrypt_rounds=4) == "skipped"  # 둘 다 비어 있을 때만 삽입


def test_reset_clears_all_app_tables_and_reseeds(db: Database) -> None:
    run_seed(db, bcrypt_rounds=4)
    with db.transaction() as conn:
        conn.execute("INSERT INTO login_attempts(scope, key, failure_count, updated_at) VALUES ('admin','account',3,'t')")
        conn.execute("DELETE FROM menus WHERE id = 1")
    assert run_seed(db, bcrypt_rounds=4, reset=True) == "seeded"
    assert _counts(db) == (len(SEED_TABLE_NUMBERS), len(SEED_MENUS))
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM login_attempts").fetchone()["n"] == 0
        assert conn.execute("SELECT MIN(id) AS m FROM menus").fetchone()["m"] == 1  # AUTOINCREMENT 초기화
        assert conn.execute("SELECT COUNT(*) AS n FROM schema_version").fetchone()["n"] == len(registered_modules())  # 버전 기록은 유지


def test_reset_data_leaves_schema(db: Database) -> None:
    run_seed(db, bcrypt_rounds=4)
    reset_data(db)
    assert _counts(db) == (0, 0)


def test_main_reports_config_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    for key in ("STORE_ID", "ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "JWT_SECRET"):
        monkeypatch.delenv(key, raising=False)
    assert seed.main([]) == 2
    assert "STORE_ID" in capsys.readouterr().err


def test_hash_password_script_prints_bcrypt_hash(tmp_path: Path) -> None:
    code = (
        "import sys, getpass; "
        "getpass.getpass = lambda prompt='': 'admin1234'; "
        "sys.path.insert(0, r'%s'); "
        "import runpy; runpy.run_path(r'%s', run_name='__main__')"
    ) % (BACKEND_DIR, BACKEND_DIR / "scripts" / "hash_password.py")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=tmp_path, check=False)
    assert out.returncode == 0, out.stderr
    printed = out.stdout.strip().splitlines()[-1]
    assert printed.startswith("$2") and verify_password("admin1234", printed)



def test_reset_also_clears_order_session_and_history_tables(seeded) -> None:  # type: ignore[no-untyped-def]
    """backend-order 테이블(FK로 서로 참조)도 순서와 무관하게 비워지고 ID가 다시 1부터 시작한다."""
    from tests.order_helpers import place, table_id_of

    tid = table_id_of(seeded, 1)
    place(seeded, tid, [(1, 2), (6, 1)])
    seeded.tables.end_session(tid)  # 이력 + 닫힌 세션
    place(seeded, tid)  # 현재 주문 + 활성 세션
    tables = ["table_sessions", "orders", "order_items", "order_history", "order_history_items"]
    with seeded.db.connection() as conn:
        assert all(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] > 0 for t in tables)

    assert run_seed(seeded.db, bcrypt_rounds=4, reset=True) == "seeded"

    with seeded.db.connection() as conn:
        assert {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables} == dict.fromkeys(tables, 0)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    fresh = place(seeded, table_id_of(seeded, 1)).order
    assert fresh.id == 1  # AUTOINCREMENT 초기화



def test_seed_menus_get_valid_image_urls(db: Database) -> None:
    from app.schemas import MenuInput, validate_menu_input
    from scripts.seed_images import SEED_MENU_IMAGES, commons_thumb_url

    assert set(SEED_MENU_IMAGES) == {name for name, *_ in SEED_MENUS}  # 모든 시드 메뉴에 사진이 있다
    assert len(set(SEED_MENU_IMAGES.values())) == len(SEED_MENU_IMAGES)  # 서로 다른 사진
    for name, url in SEED_MENU_IMAGES.items():
        # 메뉴 입력 검증(http/https URL, 2048자 이하)을 통과해야 관리자 화면에서 수정할 수 있다
        validate_menu_input(MenuInput(name=name, price=1000, description="", category="메인", image_url=url))
    # 해시 경로 규칙: 실제로 확인된 파일(Korean.food-Bibimbap-02.jpg)의 알려진 경로
    assert commons_thumb_url("Korean.food-Bibimbap-02.jpg") == (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Korean.food-Bibimbap-02.jpg/500px-Korean.food-Bibimbap-02.jpg"
    )

    run_seed(db, bcrypt_rounds=4)
    with db.connection() as conn:
        stored = {r["name"]: r["image_url"] for r in conn.execute("SELECT name, image_url FROM menus")}
    assert stored == SEED_MENU_IMAGES
