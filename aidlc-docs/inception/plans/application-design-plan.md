# Application Design 계획 (Application Design Plan)

실행 계획 승인에 따라 Application Design 단계를 시작합니다. 이 단계에서는 컴포넌트, 인터페이스, 서비스 계층, 의존성을 정합니다. 상세 비즈니스 규칙은 이후 Functional Design에서 다룹니다.

아래 질문의 `[Answer]:` 뒤에 알파벳을 적어주세요. 맞는 선택지가 없으면 `X) Other`를 고르고 설명을 적어주세요. 모든 질문에 답해야 설계 산출물을 생성합니다.

---

## Part A. 질문

## Question 1
백엔드 계층 구조는 어떻게 할까요?

A) 3계층: Router(API) → Service(업무 로직) → Repository(DB 접근)

B) 2계층: Router(API) → Service(업무 로직 + DB 접근 포함)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 2
DB 접근 방식은 무엇을 사용할까요?

A) SQLAlchemy ORM

B) SQLModel (SQLAlchemy + Pydantic 통합)

C) 표준 sqlite3 + 직접 SQL 작성

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 3
관리자 대시보드의 SSE 이벤트 전달 방식은 어떻게 할까요? (단일 서버 프로세스, 소규모 기준)

A) 서버 메모리 내 Pub/Sub (asyncio Queue): 주문/상태 변경 서비스가 이벤트를 발행하고 SSE 연결이 구독

B) SSE 엔드포인트가 DB를 짧은 주기로 조회해 변경분 전송 (예: 1초)

X) Other (please describe after [Answer]: tag below)

[Answer]: 적합한 방식을 너가 추천해주고 그걸로 진행해

## Question 4
프론트엔드 앱 구조는 어떻게 할까요?

A) 하나의 React 앱 안에서 라우트로 분리 (`/customer/*`, `/admin/*`), 공통 코드 공유

B) 고객용과 관리자용 2개의 독립된 Vite 앱

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
프론트엔드 서버 상태(API 데이터) 관리는 어떻게 할까요?

A) TanStack Query(React Query) + React Context (장바구니 등 클라이언트 상태)

B) Redux Toolkit

C) 라이브러리 없이 React 기본 훅(useState/useReducer/Context)과 fetch

X) Other (please describe after [Answer]: tag below)

[Answer]: 적합한 방식을 너가 추천해주고 그걸로 진행해

## Question 6
테이블(고객용) 인증 흐름은 어떻게 할까요? (요구사항: 로그인 정보를 로컬에 저장하고 자동 로그인)

A) 브라우저에 매장 식별자/테이블 번호/비밀번호를 저장하고, 앱 시작 시 로그인 API를 호출해 토큰을 발급받음

B) 최초 설정 시 로그인 API로 토큰만 발급받아 저장하고 이후엔 토큰만 사용 (비밀번호는 저장하지 않음)

X) Other (please describe after [Answer]: tag below)

[Answer]: 적합한 방식을 너가 추천해주고 그걸로 진행해

## Question 7
관리자 계정 설정(환경설정으로 지정) 방식은 어떻게 할까요?

A) `.env` 파일에 매장 식별자, 사용자명, bcrypt 해시된 비밀번호, JWT 시크릿 저장

B) `.env`에 평문 비밀번호를 두고 서버 시작 시 메모리에서 해시하여 사용

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8
API 경로 구성은 어떻게 할까요?

A) 역할별 prefix: `/api/customer/...`, `/api/admin/...` (인증 방식도 역할별로 분리)

B) 리소스 중심 단일 prefix: `/api/menus`, `/api/orders` ... (역할은 토큰으로 구분)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9
로컬 실행 시 프론트엔드 제공 방식은 어떻게 할까요? (Docker 미사용)

A) 프론트엔드를 빌드하여 FastAPI가 정적 파일로 서빙 (서버 1개 프로세스로 실행)

B) 개발 서버를 별도로 실행 (백엔드: uvicorn, 프론트엔드: Vite dev server, 프록시 설정)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10
프로젝트 디렉토리 구조는 어떻게 할까요?

A) 워크스페이스 루트에 `backend/`와 `frontend/` 디렉토리 분리

B) 워크스페이스 루트에 `src/server`, `src/web` 등 단일 `src/` 하위 구성

X) Other (please describe after [Answer]: tag below)

[Answer]: 적합한 방식을 너가 추천해주고 그걸로 진행해

---

## Part B. 실행 체크리스트 (승인된 답변 기준으로 수행)

### 분석
- [x] A1. requirements.md, stories.md 재확인 및 주요 비즈니스 기능 영역 식별
- [x] A2. 질문 답변 분석 및 모호성 해소 (Q3, Q5, Q6, Q10은 "추천해서 진행" 위임 -> AI 추천 확정, 근거는 components.md에 기록)

### 산출물 생성 (`aidlc-docs/inception/application-design/`)
- [x] D1. `components.md`: 컴포넌트 정의, 책임, 인터페이스
- [x] D2. `component-methods.md`: 메서드 시그니처, 목적, 입출력 타입 (상세 규칙은 Functional Design으로)
- [x] D3. `services.md`: 서비스 정의, 책임, 오케스트레이션
- [x] D4. `component-dependency.md`: 의존성 매트릭스, 통신 방식, 데이터 흐름
- [x] D5. `application-design.md`: 위 문서 통합본
- [x] D6. 설계 완전성/일관성 검증 (모든 스토리가 컴포넌트에 매핑되는지 확인)

### 마무리
- [x] F1. `aidlc-state.md`, `audit.md` 갱신
- [ ] F2. 완료 메시지 제시 및 사용자 승인 대기
