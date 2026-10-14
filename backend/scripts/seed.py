"""개발용 샘플 데이터 시드 (운영에서는 사용하지 않는다).

- 테이블 1~5번(비밀번호 1234)과 샘플 메뉴 12개를 넣는다. 매장 식별자는 .env의 STORE_ID(예: demo)를 사용한다.
- 기본: tables와 menus가 모두 비어 있을 때만 삽입한다 (여러 번 실행해도 안전).
- --reset: 모든 앱 테이블의 데이터를 지운 뒤 다시 삽입한다 (확인 프롬프트, --yes로 생략).

사용: python scripts/seed.py [--reset] [--yes]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import schema_core  # noqa: E402,F401  (core 스키마 등록)
from app.config import ConfigError, load_settings  # noqa: E402
from app.db import Database, init_schema  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.timeutil import utc_iso  # noqa: E402
from scripts.seed_images import SEED_MENU_IMAGES  # noqa: E402

SEED_TABLE_NUMBERS = [1, 2, 3, 4, 5]
SEED_TABLE_PASSWORD = "1234"

SEED_MENUS: list[tuple[str, int, str, str]] = [
    ("김치찌개", 9000, "잘 익은 김치와 돼지고기를 넣고 끓인 찌개", "메인"),
    ("된장찌개", 8500, "구수한 된장에 두부와 채소를 넣은 찌개", "메인"),
    ("제육볶음", 50000, "매콤하게 볶은 돼지고기 볶음", "메인"),
    ("비빔밥", 9500, "나물과 고추장을 곁들인 비빔밥", "메인"),
    ("계란말이", 6000, "부드러운 계란말이", "사이드"),
    ("공기밥", 1000, "갓 지은 흰쌀밥", "사이드"),
    ("김치전", 8000, "바삭하게 부친 김치전", "사이드"),
    ("콜라", 2000, "355ml 캔", "음료"),
    ("사이다", 2000, "355ml 캔", "음료"),
    ("맥주", 4500, "500ml 생맥주", "음료"),
    ("식혜", 3000, "달콤한 전통 음료", "음료"),
    ("아이스크림", 3500, "바닐라 아이스크림", "디저트"),
]


def _count(conn, table: str) -> int:  # type: ignore[no-untyped-def]
    return int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])


def reset_data(db: Database) -> None:
    """schema_version과 sqlite 내부 테이블을 제외한 모든 앱 테이블의 데이터를 지운다."""
    conn = db.connect()
    try:
        names = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' AND name != 'schema_version'"
            ).fetchall()
        ]
        conn.execute("PRAGMA foreign_keys=OFF")  # 트랜잭션 밖에서만 변경 가능
        conn.execute("BEGIN IMMEDIATE")
        for name in names:
            conn.execute(f'DELETE FROM "{name}"')
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'sqlite_sequence'").fetchone():
            conn.execute("DELETE FROM sqlite_sequence")
        conn.execute("COMMIT")
        conn.execute("PRAGMA foreign_keys=ON")
    finally:
        conn.close()


def run_seed(db: Database, *, bcrypt_rounds: int, reset: bool = False, now: datetime | None = None) -> str:
    """'seeded' 또는 'skipped'를 반환한다."""
    init_schema(db)
    if reset:
        reset_data(db)
    stamp = utc_iso(now or datetime.now(timezone.utc))
    with db.transaction() as conn:
        if _count(conn, "tables") > 0 or _count(conn, "menus") > 0:
            return "skipped"
        pw_hash = hash_password(SEED_TABLE_PASSWORD, bcrypt_rounds)
        for number in SEED_TABLE_NUMBERS:
            conn.execute(
                "INSERT INTO tables(table_number, password_hash, created_at) VALUES (?, ?, ?)",
                (number, pw_hash, stamp),
            )
        category_order: dict[str, int] = {}
        display_order: dict[str, int] = {}
        for name, price, description, category in SEED_MENUS:
            if category not in category_order:
                category_order[category] = len(category_order) + 1
            display_order[category] = display_order.get(category, 0) + 1
            conn.execute(
                "INSERT INTO menus(name, price, description, category, category_order, display_order, image_url, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    name,
                    price,
                    description,
                    category,
                    category_order[category],
                    display_order[category],
                    SEED_MENU_IMAGES.get(name),
                    stamp,
                    stamp,
                ),
            )
    return "seeded"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="개발용 샘플 데이터 시드 (운영 환경에서는 사용하지 마세요)")
    parser.add_argument("--reset", action="store_true", help="모든 앱 테이블 데이터를 지우고 다시 넣는다")
    parser.add_argument("--yes", action="store_true", help="--reset 확인 프롬프트 생략")
    args = parser.parse_args(argv)

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2

    db = Database(settings.db_path)
    print(f"대상 DB: {db.path}")
    if args.reset and not args.yes:
        answer = input("이 DB의 모든 데이터가 삭제됩니다. 계속할까요? (yes/no) ").strip().lower()
        if answer != "yes":
            print("취소했어요.")
            return 1

    result = run_seed(db, bcrypt_rounds=settings.bcrypt_rounds, reset=args.reset)
    if result == "skipped":
        print("이미 데이터가 있어 건너뛰었어요. 다시 넣으려면 --reset 을 사용하세요.")
    else:
        print(f"시드 완료: 테이블 {len(SEED_TABLE_NUMBERS)}개(비밀번호 {SEED_TABLE_PASSWORD}), 메뉴 {len(SEED_MENUS)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
