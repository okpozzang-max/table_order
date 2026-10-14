# Unit of Work 계획 (Units Generation Plan)

Application Design 승인에 따라 시스템을 구현 단위(Unit of Work)로 나눕니다.
이 프로젝트는 서버 프로세스 1개로 배포되는 모놀리스이므로 Unit은 독립 배포 단위가 아니라 **개발 순서와 설계/코드 생성의 묶음**입니다. 각 Unit은 CONSTRUCTION 단계에서 Functional Design -> Code Generation을 순서대로 거칩니다.

이미 확정된 사항: 디렉토리는 루트에 `backend/`, `frontend/` 분리 (Application Design Q10), 프론트엔드는 단일 React 앱(Q4), FastAPI가 빌드 산출물을 서빙(Q9).

아래 질문의 `[Answer]:` 뒤에 알파벳을 적어주세요. 맞는 선택지가 없으면 `X) Other`를 고르고 설명을 적어주세요.

---

## Part A. 질문

## Question 1
Unit 분할은 어떻게 할까요? (참고: 스토리 34개, 백엔드 컴포넌트 11개, 프론트엔드 모듈 3개)

A) 2개 Unit: (1) 백엔드(API + DB + SSE), (2) 프론트엔드(고객 + 관리자, 단일 React 앱)

B) 3개 Unit: (1) 백엔드, (2) 고객용 웹UI, (3) 관리자용 웹UI (코드는 한 React 앱 안의 모듈이지만 개발은 따로 진행)

C) 1개 Unit: 전체 시스템을 하나로 진행

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
백엔드 Unit의 크기는 어떻게 할까요?

A) 백엔드를 1개 Unit으로 유지

B) 백엔드를 2개 Unit으로 분리: (a) 기반 + 인증 + 메뉴 (Config, Database, Security, AuthService, MenuService), (b) 테이블 + 주문 + 실시간 (TableService, OrderService, EventBroker, SSE)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 3
Unit 구현 순서는 어떻게 할까요?

A) 백엔드 먼저 완성한 뒤 프론트엔드 (프론트엔드는 실제 API에 연결하며 개발)

B) 프론트엔드 먼저 (목 API 사용) 후 백엔드

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 4
프론트엔드 Unit에도 Functional Design 단계를 수행할까요? (실행 계획상 Functional Design은 유닛별 조건부 단계)

A) 수행: 화면 흐름, 컴포넌트 상태, 폼 검증, 오류 표시 규칙을 상세 설계

B) 생략: 스토리 인수 조건과 Application Design만으로 바로 코드 생성

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
API 타입 공유 방식은 어떻게 할까요? (백엔드 Pydantic 모델 <-> 프론트엔드 TypeScript 타입)

A) FastAPI가 생성하는 OpenAPI 스키마에서 TypeScript 타입을 자동 생성

B) 프론트엔드에서 TypeScript 타입을 수동 작성

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
테스트 범위는 어디까지 할까요? (Property-Based Testing 확장은 비활성)

A) 백엔드: pytest 단위 + API 통합 테스트 / 프론트엔드: Vitest + React Testing Library 컴포넌트 테스트

B) 백엔드 pytest(단위 + API 통합 테스트)만 작성, 프론트엔드는 수동 확인

C) A에 더해 브라우저 E2E 테스트(Playwright)까지

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
로컬 데모/검증용 초기 데이터(시드)를 제공할까요?

A) 제공: 샘플 메뉴(카테고리 여러 개)와 샘플 테이블 몇 개를 넣는 시드 스크립트

B) 제공하지 않음 (관리자 화면에서 직접 등록)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Part A-2. 후속 질문 (답변 분석 결과 확인이 필요한 항목)

답변을 분석한 결과 아래 모호한 점/충돌이 있어 추가 질문을 드립니다.

- Q1(A: 2개 Unit, 백엔드 1개)과 Q2(B: 백엔드를 2개로 분리)가 서로 어긋납니다. 최종 Unit 수를 확정해야 합니다.
- Q3(B: 프론트엔드 먼저, 목 API 사용)와 Q5(A: 백엔드 OpenAPI에서 TS 타입 자동 생성)가 충돌합니다. 프론트엔드를 먼저 만들면 생성 대상인 백엔드가 아직 없습니다.
- 백엔드가 2개로 나뉘는 경우, 프론트엔드와의 구현 순서가 정해져 있지 않습니다.

## Question 8 (Q1/Q2 충돌 확인)
최종 Unit 구성은 어떻게 할까요?

A) 3개 Unit: (1) 프론트엔드(고객 + 관리자 단일 React 앱), (2) 백엔드 코어(Config, Database, Security, AuthService, MenuService), (3) 백엔드 주문/실시간(TableService, OrderService, EventBroker, SSE)

B) 2개 Unit: 프론트엔드 + 백엔드 (Q2의 분리 요청은 취소)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 (Q3/Q5 충돌 확인)
프론트엔드를 먼저 만들 때 API 계약과 타입은 어떻게 확보할까요?

A) 계약 우선(contract-first): 프론트엔드 시작 전에 Application Design의 API 표를 바탕으로 `openapi.yaml`을 먼저 작성하고, 이 파일에서 TS 타입과 목 API를 만든다. 이후 백엔드는 이 계약대로 구현하고 FastAPI가 생성하는 OpenAPI와 일치하는지 검증한다.

B) 프론트엔드에서 TS 타입을 수동 작성하고 목 API로 개발한다. 백엔드 완성 후 생성된 OpenAPI와 대조해 타입을 맞춘다 (Q5 자동 생성은 백엔드 완료 후 적용).

C) 구현 순서를 백엔드 먼저로 변경한다 (Q3을 A로 수정). 이 경우 Q5의 자동 생성을 그대로 사용한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: 너가 추천해서 그걸로 진행해

## Question 10 (구현 순서 확인)
Q8에서 3개 Unit을 선택한 경우 구현 순서는 어떻게 할까요? (Q8에서 B 또는 Q9에서 C를 선택했다면 이 질문은 "해당 없음"이라고 적어주세요)

A) 프론트엔드 -> 백엔드 코어 -> 백엔드 주문/실시간

B) 백엔드 코어 -> 프론트엔드 -> 백엔드 주문/실시간 (프론트엔드는 인증/메뉴 화면은 실제 API, 주문/실시간 화면은 목 API 사용)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11 (목 API 방식)
프론트엔드를 목 API로 개발하는 경우 목 방식은 무엇으로 할까요? (Q9에서 C를 선택했다면 "해당 없음"이라고 적어주세요)

A) MSW(Mock Service Worker): 브라우저 개발 실행과 Vitest 테스트에서 같은 핸들러를 공용으로 사용

B) 프론트엔드 내부 인-메모리 가짜 API 모듈 (코드에서 실제 ApiClient 대신 교체)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Part A-3. 확정 사항 요약 (답변 분석 결과)

| 항목 | 확정 내용 | 근거 |
|---|---|---|
| Unit 수 | 3개 Unit | Q8: A (Q1/Q2 충돌 해소) |
| Unit 1 | `frontend` - 고객 + 관리자 단일 React 앱 | Q1: A, Q8: A |
| Unit 2 | `backend-core` - Config, Database, Security, Auth Deps, AuthService, MenuService, 인증/메뉴 라우터, App Entry | Q2: B, Q8: A |
| Unit 3 | `backend-order` - TableService, OrderService, EventBroker, SSE, 주문/테이블 라우터 | Q2: B, Q8: A |
| 구현 순서 | frontend -> backend-core -> backend-order | Q3: B, Q10: A |
| 프론트엔드 Functional Design | 수행 | Q4: A |
| API 계약/타입 | **계약 우선(contract-first)** - AI 추천. 프론트엔드 Unit 초반에 `contracts/openapi.yaml`을 작성(Application Design의 API 표 기준), 여기서 TS 타입을 자동 생성. 백엔드 Unit은 이 계약을 구현하고 FastAPI가 생성한 OpenAPI와 일치하는지 테스트로 검증 | Q9: 위임, Q5: A 유지 |
| 목 API 방식 | 프론트엔드 내부 인-메모리 가짜 API 모듈 (생성된 TS 타입을 사용, 실제 ApiClient 대신 교체) | Q11: B |
| 테스트 | 백엔드 pytest(단위 + API 통합), 프론트엔드 Vitest + React Testing Library | Q6: A |
| 시드 | 샘플 메뉴/테이블 시드 스크립트 제공 (backend-core에 메뉴/테이블 시드, 필요 시 backend-order에서 보강) | Q7: A |

### Q9 추천 근거 (계약 우선)
- 프론트엔드를 먼저 만들되 Q5의 "OpenAPI에서 TS 타입 자동 생성"을 포기하지 않아도 된다.
- 계약 파일 하나가 프론트엔드 타입, 가짜 API 응답 형태, 백엔드 구현 검증의 공통 기준이 되어, 나중에 프론트엔드와 백엔드를 연결할 때의 불일치를 줄인다.
- 비용: 프론트엔드 시작 전에 계약 작성이 필요하다. Application Design에 API 표(19개 경로)가 이미 있어 부담이 작다.
- 백엔드에서 계약 변경이 필요해지면 `contracts/openapi.yaml`을 수정하고 프론트엔드 타입을 재생성한다.

### 영향을 받는 이후 단계
- 각 Unit은 Functional Design -> Code Generation을 순서대로 거친다 (NFR/Infra 단계는 실행 계획대로 생략).
- Unit 1(frontend)은 백엔드 없이 가짜 API로 실행/테스트할 수 있어야 한다.
- 전체 통합(실제 백엔드 연결)은 Unit 3 완료 후 Build and Test 단계에서 검증한다.

---

## Part B. 실행 체크리스트 (승인 후 수행)

### 분석
- [x] A1. 승인된 답변에 따라 Unit 경계와 순서 확정 (Part A-3 참고)
- [x] A2. 답변 모호성 점검 (충돌 2건 발견 -> 후속 질문 Q8~Q11로 해소 완료)

### 산출물 생성 (`aidlc-docs/inception/application-design/`)
- [x] U1. `unit-of-work.md`: Unit 정의, 책임, 포함 컴포넌트, 코드 조직 전략(Greenfield 디렉토리 구조)
- [x] U2. `unit-of-work-dependency.md`: Unit 간 의존성 매트릭스와 구현 순서
- [x] U3. `unit-of-work-story-map.md`: 스토리 34개의 Unit 매핑
- [x] U4. Unit 경계/의존성 검증 (backend-core -> backend-order 역의존 방지: MenuService 이벤트 발행기 선택적 주입)
- [x] U5. 모든 스토리가 Unit에 할당되었는지 확인 (13 + 18 + 3 = 34)

### 마무리
- [x] F1. `aidlc-state.md`, `audit.md` 갱신
- [ ] F2. 완료 메시지 제시 및 사용자 승인 대기
