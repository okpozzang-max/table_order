# Unit of Work (작업 단위 정의)

근거: `aidlc-docs/inception/plans/unit-of-work-plan.md` (Q1~Q11, 확정 요약 Part A-3)

이 시스템은 서버 프로세스 1개로 배포되는 **모놀리스**입니다. Unit은 독립 배포 단위가 아니라 개발 순서와 설계/코드 생성 단위입니다. 각 Unit은 Functional Design -> Code Generation을 거칩니다 (NFR Requirements, NFR Design, Infrastructure Design은 실행 계획에 따라 생략).

## Unit 개요

| 순서 | Unit | 한 줄 설명 | 주요 산출물 |
|---|---|---|---|
| 1 | `frontend` | 고객용 + 관리자용 웹UI (단일 React 앱) | `frontend/`, `contracts/openapi.yaml`, 가짜 API |
| 2 | `backend-core` | 기반, 인증, 메뉴 | `backend/` 기반 코드, 인증/메뉴 API, 시드 |
| 3 | `backend-order` | 테이블 세션, 주문, 실시간(SSE) | 테이블/주문/SSE API |

---

## Unit 1. frontend

**책임**
- 고객용 화면: 테이블 설정/자동 로그인, 메뉴, 장바구니, 주문 확인/결과, 현재 세션 주문 내역(폴링)
- 관리자용 화면: 로그인, 대시보드(SSE 수신), 주문 상세/상태 변경/삭제, 테이블 등록/이용 완료/과거 내역, 메뉴 관리
- **API 계약 작성**: `contracts/openapi.yaml`을 Unit 초반에 작성 (Application Design의 API 표 19개 경로 기준). 이 파일에서 TS 타입을 자동 생성
- **가짜 API**: 인-메모리 가짜 API 모듈로 백엔드 없이 실행/테스트 가능하게 한다 (실제 ApiClient 대신 교체, 생성된 TS 타입 사용). SSE도 가짜 이벤트 소스로 대체
- 오류/예외 화면 동작 (EP-E의 프론트엔드 부분)

**포함 컴포넌트** (components.md 기준): FC-1 Shared, FC-2 Customer, FC-3 Admin, FC-4 App Shell

**포함하지 않는 것**: 서버 로직, DB, 실제 SSE 서버

**Definition of Done**
- 가짜 API 위에서 모든 화면 흐름이 동작한다.
- Vitest + React Testing Library 컴포넌트 테스트 통과
- `contracts/openapi.yaml`이 19개 경로와 요청/응답/오류 형식을 포함한다.
- 프론트엔드 빌드(`npm run build`) 성공

**설계 단계**: Functional Design 수행 (화면 흐름, 컴포넌트 상태, 폼 검증, 오류 표시 규칙, localStorage 스키마, 폴링 주기)

---

## Unit 2. backend-core

**책임**
- 프로젝트 기반: Config(`.env`), Database(연결/트랜잭션/스키마 부트스트랩), Security(bcrypt/JWT), Auth Deps, App Entry(`main.py`, 정적 서빙, 공통 예외 처리)
- AuthService: 관리자 로그인(잠금 포함), 테이블 로그인, 토큰 발급
- MenuService: 메뉴 조회/CRUD/순서/검증
- 라우터: `customer_auth`, `customer_menu`, `admin_auth`, `admin_menus`
- 스키마: 인증/메뉴/테이블 관련 테이블(menus, tables, login_attempts)과 스키마 확장 메커니즘 제공
- 시드 스크립트: 샘플 메뉴(여러 카테고리)와 샘플 테이블 몇 개
- 계약 검증 테스트: FastAPI가 생성한 OpenAPI가 `contracts/openapi.yaml`의 해당 경로와 일치하는지 확인

**포함 컴포넌트**: BC-1, BC-2, BC-3, BC-4, BC-6, BC-7, BC-10(일부 라우터), BC-11

**설계 노트**
- MenuService는 이벤트 발행기를 **선택적 주입**으로 받는다(기본은 아무 동작 안 함). EventBroker는 backend-order에 있으므로, backend-core가 backend-order에 의존하지 않게 하기 위한 의존성 역전이다. backend-order에서 실제 EventBroker를 연결하면 `menu_changed` 이벤트가 발행된다.
- `tables` 테이블 스키마는 backend-core가 소유한다. 테이블 로그인(AuthService)이 이 테이블을 조회하기 때문이다. 테이블 **등록** API는 backend-order(TableService)가 제공하며, backend-core 단계에서는 시드 스크립트로 테이블을 만든다.

**Definition of Done**
- pytest 단위 + API 통합 테스트 통과 (로그인/잠금/JWT 만료/메뉴 CRUD/검증)
- OpenAPI 계약 일치 테스트 통과
- 시드 실행 후 관리자 로그인과 메뉴 조회가 동작한다.

**설계 단계**: Functional Design 수행 (스키마, 잠금 규칙 상세, 검증 값, 토큰 클레임)

---

## Unit 3. backend-order

**책임**
- TableService: 테이블 등록, 세션 시작/종료, 이력 이관, 과거 내역 조회
- OrderService: 주문 생성(서버 금액 재계산), 현재 세션 주문 조회, 대시보드 스냅샷, 주문 상세, 순차 상태 전이, 삭제
- EventBroker와 SSE 스트림(`/api/admin/events`), keep-alive
- 라우터: `customer_orders`, `admin_orders`, `admin_tables`
- 스키마 확장: table_sessions, orders, order_items, order_history 등
- MenuService에 EventBroker 연결 (`menu_changed` 발행)
- 계약 검증 테스트: 주문/테이블/SSE 경로의 OpenAPI 일치
- 전체 통합: 프론트엔드 빌드 산출물을 FastAPI가 서빙하고, 가짜 API 대신 실제 API로 전환하여 end-to-end 흐름 확인

**포함 컴포넌트**: BC-5, BC-8, BC-9, BC-10(나머지 라우터)

**Definition of Done**
- pytest 단위 + API 통합 테스트 통과 (주문 생성/금액 재계산/세션 시작·종료/이력 이관/상태 전이/삭제/SSE 이벤트)
- 신규 주문이 SSE로 2초 이내 전달됨을 검증하는 테스트
- 프론트엔드가 실제 백엔드와 연결되어 주요 시나리오가 동작한다.

**설계 단계**: Functional Design 수행 (주문/세션/이력 스키마, 상태 전이 표, 트랜잭션 경계, 주문 번호 규칙, 이벤트 페이로드)

---

## 코드 조직 전략 (Greenfield)

애플리케이션 코드는 워크스페이스 루트에 두고, 문서는 `aidlc-docs/`에만 둡니다.

```
table_order/
+-- contracts/
|   +-- openapi.yaml              (Unit 1에서 작성)
+-- frontend/                     (Unit 1)
|   +-- package.json
|   +-- vite.config.ts
|   +-- src/
|       +-- app/                  (라우트, 프로바이더)
|       +-- shared/               (ApiClient, useEventStream, UI, 생성된 API 타입)
|       +-- customer/
|       +-- admin/
|       +-- mocks/                (인-메모리 가짜 API)
+-- backend/                      (Unit 2, 3)
|   +-- requirements.txt
|   +-- .env.example
|   +-- app/
|   |   +-- main.py, config.py, db.py, security.py, deps.py   (Unit 2)
|   |   +-- events.py                                         (Unit 3)
|   |   +-- services/             (auth, menu: Unit 2 / table, order: Unit 3)
|   |   +-- routers/              (customer_auth, customer_menu,
|   |                              admin_auth, admin_menus: Unit 2 /
|   |                              customer_orders, admin_orders,
|   |                              admin_tables: Unit 3)
|   +-- scripts/
|   |   +-- seed.py               (Unit 2)
|   +-- tests/
+-- README.md                     (실행 방법: Build and Test 단계에서 최종 정리)
+-- aidlc-docs/                   (문서 전용)
```

- 프론트엔드 테스트(`*.test.tsx`)는 소스 옆에 두거나 `frontend/tests/`에 둔다. 최종 위치는 Unit 1 Code Generation 계획에서 확정한다.
- 프론트엔드 빌드 산출물(`frontend/dist`)은 FastAPI가 정적 서빙한다.
- 로컬 실행은 Docker 없이 Python 가상환경과 Node.js로 한다.
- 위 구조는 Unit별 Code Generation 계획에서 구체 파일 목록으로 확정한다.
