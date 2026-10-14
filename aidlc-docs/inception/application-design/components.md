# Components (컴포넌트 정의)

설계 결정의 근거는 `application-design-plan.md`(Q1~Q10)와 아래 "설계 결정" 표를 참고합니다.

## 설계 결정 요약

| 항목 | 결정 | 출처 |
|---|---|---|
| 백엔드 계층 | 2계층: Router → Service (Service가 DB 접근 포함) | Q1: B |
| DB 접근 | 표준 `sqlite3` + 직접 SQL (ORM 없음) | Q2: C |
| SSE 전달 | 서버 메모리 내 Pub/Sub (asyncio) - AI 추천 | Q3: 위임 |
| 프론트엔드 구조 | 단일 React 앱, 라우트로 `/customer/*`, `/admin/*` 분리 | Q4: A |
| 프론트엔드 상태 | TanStack Query + React Context - AI 추천 | Q5: 위임 |
| 테이블 인증 | 로컬에 매장ID/테이블번호/비밀번호 저장, 시작 시 로그인 API 호출해 토큰 발급 - AI 추천 | Q6: 위임 |
| 관리자 계정 | `.env`에 매장ID, 사용자명, bcrypt 해시, JWT 시크릿 | Q7: A |
| API 경로 | `/api/customer/...`, `/api/admin/...` 역할별 prefix | Q8: A |
| 프론트 제공 | 빌드 후 FastAPI 정적 서빙 (프로세스 1개) | Q9: A |
| 디렉토리 | 루트에 `backend/`, `frontend/` 분리 - AI 추천 | Q10: 위임 |

### AI 추천 결정의 근거
- **Q3 (메모리 Pub/Sub)**: 단일 매장, 최대 약 20개 테이블, 서버 프로세스 1개이므로 외부 브로커가 불필요하고, DB 폴링보다 지연이 적어 2초 이내 반영(NFR-1)을 쉽게 만족한다. 단점(재시작 시 연결 유실, 다중 프로세스 불가)은 클라이언트 자동 재연결과 재연결 시 전체 재조회로 보완한다.
- **Q5 (TanStack Query + Context)**: 고객 화면의 5~10초 폴링(`refetchInterval`), 캐시 무효화, 재시도, 관리자 SSE 수신 후 재조회가 라이브러리 기본 기능으로 해결된다. 장바구니와 인증 정보는 소규모 클라이언트 상태라 Context로 충분하다.
- **Q6 (자격 증명 저장 후 시작 시 로그인)**: 요구사항이 "로그인 정보 로컬 저장, 저장된 정보로 자동 로그인"을 명시한다. 토큰이 16시간 후 만료되어도 저장된 정보로 조용히 재로그인할 수 있다. 비밀번호가 브라우저에 평문으로 남는 점은 전용 태블릿 전제의 수용된 트레이드오프이며, 서버에는 해시로만 저장한다.
- **Q10 (`backend/`, `frontend/` 분리)**: 두 기술 스택(Python, Node)의 의존성, 테스트, 빌드가 독립적으로 관리된다.

---

## 시스템 구성

```
+--------------------+      +--------------------+
| Customer Web UI    |      | Admin Web UI       |
| (React /customer)  |      | (React /admin)     |
+---------+----------+      +---------+----------+
          |  REST (JSON)              |  REST + SSE
          v                           v
+------------------------------------------------+
| FastAPI Backend (single process)               |
|  Routers -> Services -> sqlite3                |
|  EventBroker (in-memory pub/sub)               |
+------------------------+-----------------------+
                         |
                         v
                 +---------------+
                 | SQLite (file) |
                 +---------------+
```

---

## 백엔드 컴포넌트 (`backend/app/`)

### BC-1. Config (`config.py`)
- **목적**: `.env`에서 설정을 읽는다.
- **책임**: 매장 식별자, 관리자 사용자명, 관리자 비밀번호 해시(bcrypt), JWT 시크릿, DB 파일 경로, 세션/토큰 유효시간(16h), 로그인 잠금 정책(5회/15분) 제공
- **인터페이스**: `get_settings() -> Settings`

### BC-2. Database (`db.py`)
- **목적**: SQLite 연결과 트랜잭션 관리, 스키마 초기화
- **책임**: 요청 단위 연결 생성(WAL 모드, 외래키 활성화), 트랜잭션 컨텍스트 제공, 시작 시 스키마 생성
- **인터페이스**: `get_connection()`, `transaction()`, `init_schema()`

### BC-3. Security (`security.py`)
- **목적**: 비밀번호 해싱과 JWT 처리
- **책임**: bcrypt 해시/검증, 관리자·테이블 JWT 발급 및 검증 (역할 클레임 포함)
- **인터페이스**: `hash_password`, `verify_password`, `create_token`, `decode_token`

### BC-4. Auth Dependencies (`deps.py`)
- **목적**: 라우터에서 사용할 인증/인가 의존성
- **책임**: Authorization 헤더의 JWT를 검증하여 관리자 또는 테이블 주체를 반환, 실패 시 401
- **인터페이스**: `require_admin()`, `require_table()`

### BC-5. EventBroker (`events.py`)
- **목적**: 서버 메모리 기반 이벤트 발행/구독
- **책임**: 구독자별 asyncio Queue 관리, 서비스(스레드풀 실행)에서 안전하게 발행, 구독 해제 처리
- **인터페이스**: `publish(event)`, `subscribe() -> AsyncIterator[event]`

### BC-6. AuthService (`services/auth_service.py`)
- **목적**: 관리자와 테이블의 인증 업무
- **책임**: 관리자 로그인(매장ID/사용자명/비밀번호 검증, 실패 횟수 기록과 잠금), 테이블 로그인(매장ID/테이블번호/비밀번호 검증), 토큰 발급
- **스토리**: US-A1.1, US-A1.2, US-C1.1, US-E3, US-E4, US-E9

### BC-7. MenuService (`services/menu_service.py`)
- **목적**: 메뉴 조회와 관리
- **책임**: 카테고리별 메뉴 조회(노출 순서 반영), 등록/수정/삭제, 노출 순서 변경, 입력 검증(필수값, 가격 범위)
- **스토리**: US-C2.1, US-C2.2, US-A4.1~A4.4, US-E7

### BC-8. TableService (`services/table_service.py`)
- **목적**: 테이블 등록과 테이블 세션 라이프사이클
- **책임**: 테이블 등록/비밀번호 설정, 현재 활성 세션 조회, 세션 시작(첫 주문 시), 세션 종료(이용 완료)와 주문 이력 이관, 과거 이력 조회(날짜 필터)
- **스토리**: US-A3.1, US-A3.3, US-A3.4, US-E8

### BC-9. OrderService (`services/order_service.py`)
- **목적**: 주문 생성과 관리
- **책임**: 주문 생성(메뉴 검증, 서버 측 금액 재계산, 세션 확보), 현재 세션 주문 조회(고객용, 페이지네이션), 대시보드용 테이블별 요약 조회(관리자), 상태 전이(순차만 허용), 주문 삭제와 합계 재계산, 변경 시 이벤트 발행
- **스토리**: US-C4.1, US-C4.2, US-C5.1, US-C5.2, US-A2.1~A2.5, US-A3.2, US-E1, US-E2, US-E5, US-E8

### BC-10. API Routers (`routers/`)
- **목적**: HTTP 인터페이스, 입력 스키마 검증, 서비스 호출
- **구성**:
  - `customer_auth`, `customer_menu`, `customer_orders` (`/api/customer/...`)
  - `admin_auth`, `admin_orders` (SSE 스트림 포함), `admin_tables`, `admin_menus` (`/api/admin/...`)
- **책임**: 요청/응답 모델(Pydantic) 정의, 인증 의존성 적용, 도메인 오류를 HTTP 상태코드로 변환

### BC-11. App Entry (`main.py`)
- **목적**: 애플리케이션 조립
- **책임**: 라우터 등록, 스키마 초기화, 프론트엔드 빌드 산출물 정적 서빙 및 SPA 라우팅 폴백, 공통 예외 처리

---

## 프론트엔드 컴포넌트 (`frontend/src/`)

### FC-1. Shared (`shared/`)
- **ApiClient**: fetch 래퍼. 베이스 URL, 토큰 헤더, 오류 정규화, 401 처리
- **SSE 클라이언트 훅 (`useEventStream`)**: Authorization 헤더를 사용하는 fetch 기반 SSE 수신, 끊김 시 자동 재연결, 재연결 시 콜백 호출
- **공통 UI**: 버튼(최소 44x44px), 확인 팝업, 토스트/피드백, 카드, 로딩/오류 표시
- **타입/유틸**: API 타입, 금액 포맷터

### FC-2. Customer 모듈 (`customer/`)
- **TableAuthProvider**: localStorage의 자격 증명으로 시작 시 로그인, 만료 시 재로그인, 실패 시 설정 화면 이동
- **CartProvider**: 장바구니 상태와 localStorage 동기화 (추가, 삭제, 수량, 비우기, 합계)
- **TableSetupPage**: 매장ID/테이블번호/비밀번호 입력 (초기 설정)
- **MenuPage**: 카테고리 탭, 메뉴 카드 그리드, 담기
- **CartPanel**: 장바구니 목록, 수량 조절, 합계, 주문하기
- **OrderConfirmView / OrderResultView**: 최종 확인, 성공(주문 번호, 5초 후 이동)/실패 표시
- **OrderHistoryPage**: 현재 세션 주문 목록, 상태 표시, 폴링 갱신

### FC-3. Admin 모듈 (`admin/`)
- **AdminAuthProvider / LoginPage**: 로그인, 토큰 보관, 만료 처리
- **DashboardPage**: 테이블 카드 그리드, 테이블 필터, SSE로 갱신, 신규 주문 강조
- **TableCard / OrderDetailModal**: 총 주문액, 최신 주문 미리보기, 상세, 상태 변경, 주문 삭제
- **TableManagement**: 테이블 등록/비밀번호 설정, 이용 완료 처리
- **TableHistoryModal**: 과거 주문 목록, 날짜 필터, 닫기
- **MenuManagementPage**: 메뉴 목록, 등록/수정 폼, 삭제, 순서 조정

### FC-4. App Shell (`app/`)
- 라우터 구성(`/customer/*`, `/admin/*`), QueryClientProvider, 보호 라우트

---

## 컴포넌트 인터페이스 요약

| 컴포넌트 | 제공 | 사용 |
|---|---|---|
| Routers | HTTP API | Services, Deps |
| Services | 업무 메서드 | Database, Security, EventBroker, Config |
| EventBroker | publish/subscribe | (Services가 발행, admin_orders 라우터가 구독) |
| ApiClient | 타입 있는 요청 함수 | Customer/Admin 모듈 |
| Providers | 인증/장바구니 컨텍스트 | 페이지 컴포넌트 |
