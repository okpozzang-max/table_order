# Build Instructions

테이블오더는 로컬 프로세스로 실행하는 모놀리스입니다 (Docker 미사용). 프론트엔드(React 정적 빌드)와 백엔드(FastAPI + SQLite)를 각각 준비하고, 백엔드가 `frontend/dist`를 서빙합니다.

## Prerequisites

| 항목 | 내용 |
|---|---|
| OS | Windows (PowerShell). macOS/Linux도 동일 명령에서 가상환경 활성화 경로만 다름 |
| Python | 3.14 (개발·검증 환경: 3.14.4). `python --version` 으로 확인 |
| Node.js / npm | 프론트엔드 빌드용. `frontend/package-lock.json` 기준 (`node --version`, `npm --version`) |
| 백엔드 의존성 | `backend/requirements.txt`(직접, `==` 고정), `requirements-dev.txt`(테스트), `requirements.lock.txt`(전이 의존성 포함 검증된 전체 목록) |
| 디스크/메모리 | 소규모 (DB 파일 1개, 프로세스 1개) |
| 환경 변수 | 필수 `STORE_ID`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `JWT_SECRET`(32자 이상). 선택 키는 `backend/.env.example` 참고 (`DB_PATH`, `TIMEZONE`, `SSE_*` 등) |

## Build Steps

### 1. 백엔드 의존성 설치

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt        # 런타임 + 테스트 도구
pip check                                   # 기대: No broken requirements found.
```

검증 결과: 새 가상환경에 `requirements-dev.txt` 만 설치하면 `pip freeze` 가 `requirements.lock.txt` 와 같은 패키지 29개/버전으로 고정된다 (`tzdata==2026.5` 포함).

### 2. 백엔드 설정

```powershell
copy .env.example .env                      # 개발용 값. 운영 전에는 JWT_SECRET, 관리자 해시를 반드시 교체
python scripts/hash_password.py             # (선택) 새 관리자 비밀번호 해시 -> .env 의 ADMIN_PASSWORD_HASH 에 작은따옴표로 감싸서
```

### 3. 프론트엔드 설치와 빌드

```powershell
cd ..\frontend
npm install
npm run gen:api                             # contracts/openapi.yaml -> 타입 (계약이 바뀐 경우)
npm run build                               # 타입 검사 + 프로덕션 빌드 (VITE_API_MODE=real, .env.production)
```

### 4. 빌드 확인

- 프론트엔드: `frontend/dist/index.html` 과 `frontend/dist/assets/*.js, *.css` 생성. 검증 시 JS 382 kB(gzip 117 kB), CSS 21.7 kB, 빌드 약 0.3초.
- 백엔드: 별도 컴파일 단계 없음. 앱이 import 되고 설정이 올바른지 확인:

```powershell
cd ..\backend
python -c "from app.main import create_app; print('import ok')"
```

- 서버 기동 확인 (선택):

```powershell
python scripts/seed.py
python -m uvicorn app.main:create_app --factory --port 8000 --timeout-graceful-shutdown 5
# 다른 터미널: curl.exe http://localhost:8000/api/openapi.json  -> 200
```

### 생성물

| 산출물 | 위치 |
|---|---|
| 프론트엔드 정적 파일 | `frontend/dist/` |
| SQLite DB | `backend/data/table_order.sqlite3` (`DB_PATH` 로 변경, 시작 시 자동 생성·스키마 적용) |
| 테스트 임시 파일 | `backend/.pytest_tmp` (git 제외) |

### 허용되는 경고

- pytest: Starlette `TestClient` 가 `httpx` 사용 중단 예고(`httpx2` 권장)를 출력한다. 동작에는 영향이 없다.
- vitest: React Testing Library의 `act(...)` 안내 메시지가 일부 테스트에서 출력될 수 있다 (통과에 영향 없음).

## Troubleshooting

### 서버가 시작되지 않고 "설정 오류: ... 항목을 확인해주세요"가 나온다
- 원인: 필수 키 누락, `JWT_SECRET` 32자 미만, `ADMIN_PASSWORD_HASH` 가 bcrypt 형식이 아님, `TIMEZONE`/숫자 설정 오류. 메시지에는 키 이름만 나온다 (값은 출력하지 않음).
- 해결: `backend/.env` 를 `.env.example` 과 비교. 해시의 `$` 때문에 값을 **작은따옴표**로 감싸야 한다.

### `ZoneInfoNotFoundError` / `TIMEZONE` 오류
- 원인: Windows에는 IANA 시간대 데이터가 없다.
- 해결: `pip install -r requirements.txt` 로 `tzdata` 설치 여부 확인.

### `pip install` 이 실패한다
- 원인: Python 버전 불일치(휠 없음) 또는 네트워크.
- 해결: Python 3.14 사용, `pip install --upgrade pip` 후 재시도. 다른 Python 버전을 쓸 경우 `requirements.lock.txt` 와 달라질 수 있으니 테스트로 확인.

### 서버 화면은 뜨는데 `/` 에서 "API만 제공" 로그가 나온다
- 원인: `frontend/dist` 가 없음. 해결: `cd frontend; npm run build`. 다른 경로면 `FRONTEND_DIST` 설정.

### Ctrl+C 후 서버가 종료되지 않는 것처럼 보인다
- 원인: 열린 관리자 실시간 연결(SSE)을 uvicorn이 닫히기를 기다린다.
- 해결: 실행 명령에 `--timeout-graceful-shutdown 5` 사용 (지정한 초 뒤 강제 정리).

### 프론트엔드 빌드에서 타입 오류
- 원인: 계약 변경 후 타입 미재생성. 해결: `npm run gen:api` 후 다시 빌드.
