"""관리자 비밀번호의 bcrypt 해시를 만든다 (.env의 ADMIN_PASSWORD_HASH 값).

사용: python scripts/hash_password.py
비밀번호는 화면에 표시되지 않는 프롬프트로 입력한다. (인자로 넘기면 셸 기록에 남을 수 있어 지원하지 않는다)
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.security import hash_password  # noqa: E402


def main() -> int:
    first = getpass.getpass("관리자 비밀번호: ")
    second = getpass.getpass("한 번 더 입력: ")
    if first != second:
        print("두 입력이 달라요.", file=sys.stderr)
        return 1
    if not first:
        print("비밀번호가 비어 있어요.", file=sys.stderr)
        return 1
    try:
        print(hash_password(first))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
