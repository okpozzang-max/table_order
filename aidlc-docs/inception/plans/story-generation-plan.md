# User Stories 생성 계획 (Story Generation Plan)

요구사항 문서(`aidlc-docs/inception/requirements/requirements.md`)를 사용자 중심 스토리로 변환하는 방법을 정하는 계획서입니다.
아래 질문의 `[Answer]:` 뒤에 알파벳을 적어주세요. 맞는 선택지가 없으면 `X) Other`를 고르고 설명을 적어주세요. 모든 질문에 답해야 다음 단계로 진행합니다.

---

## Part A. 스토리 분해 방식 옵션 (참고)

| 방식 | 설명 | 장점 | 단점 |
|---|---|---|---|
| User Journey 기반 | 사용자의 업무 흐름 순서대로 스토리 구성 (예: 주문 흐름, 테이블 운영 흐름) | 흐름과 맥락 파악이 쉬움 | 기능 간 중복 가능 |
| Feature 기반 | 기능 단위로 스토리 구성 (메뉴, 장바구니, 주문 ...) | 요구사항(FR-*)과 1:1 추적이 쉬움 | 사용자 흐름이 흩어질 수 있음 |
| Persona 기반 | 고객 / 관리자별로 묶음 | 화면(고객용/관리자용)과 구조가 일치 | 두 페르소나 간 연결 흐름이 약함 |
| Epic 기반 | Epic - Story 계층 구조 | 큰 그림과 세부를 함께 표현 | 문서가 길어짐 |

---

## Part B. 질문

## Question 1
스토리 분해 방식은 어느 것을 사용할까요?

A) Persona 기반 위에 Feature 단위 Epic으로 구성 (예: 고객 > 메뉴 조회 Epic > 스토리들)

B) Feature 기반 (기능별로 나열, 페르소나는 스토리 안에 표기)

C) User Journey 기반 (주문 흐름, 테이블 운영 흐름 등 흐름 순서)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
스토리 작성 형식은 어떻게 할까요?

A) "As a [페르소나], I want [기능], so that [이유]" 형식을 한국어로 번역하여 작성 ("[페르소나]로서 [기능]을 원한다. 그래야 [이유]")

B) 영어 표준 형식 그대로 사용

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
인수 조건(Acceptance Criteria) 형식은 어떻게 할까요?

A) Given / When / Then (시나리오 형식)

B) 체크리스트 형식 (조건을 글머리표로 나열)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
스토리 세분화 수준은 어떻게 할까요?

A) 중간: 요구사항의 하위 기능(FR-C1.1 등) 단위 묶음 정도 (전체 약 20~25개 스토리)

B) 세밀: 요구사항 항목마다 개별 스토리 (전체 30개 이상)

C) 큼직: 요구사항의 큰 기능 단위(FR-C1, FR-A2 등) 1개당 스토리 1개 (전체 약 10~12개)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
페르소나는 어떻게 정의할까요?

A) 2개: 고객(테이블 이용자), 매장 관리자

B) 3개: 고객, 매장 관리자, 그리고 테이블 태블릿 초기 설정을 수행하는 설치 담당자(관리자와 별도 역할로 구분)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
스토리에 우선순위(MoSCoW 등)를 표기할까요? (요구사항은 모두 MVP 범위)

A) 표기하지 않음 (전부 MVP 필수)

B) Must / Should / Could로 표기 (예: 고객 주문 상태 폴링은 Should)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
스토리에 오류/엣지 케이스(주문 실패, 로그인 잠금, 잘못된 상태 전이, SSE 재연결 등)는 어떻게 반영할까요?

A) 각 스토리의 인수 조건에 함께 포함

B) 별도 "오류/예외 처리" 스토리로 분리

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 8
스토리와 요구사항의 추적성(traceability)은 어떻게 표시할까요?

A) 각 스토리에 관련 요구사항 ID(FR-C4.2 등)를 명시

B) 별도 추적성 표를 문서 끝에 추가

C) 둘 다

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Part C. 생성 실행 체크리스트 (승인 후 진행) -체크리스트 승인

### 페르소나
- [x] P1. 요구사항에서 사용자 유형 추출 및 Q5 답변에 따라 페르소나 확정
- [x] P2. `personas.md` 작성 (특성, 목표, 사용 환경, 불편 사항)

### 스토리
- [x] S1. Q1 답변에 따른 Epic/구조 확정
- [x] S2. 고객용 스토리 작성 (자동 로그인, 메뉴 조회, 장바구니, 주문 생성, 주문 내역 조회)
- [x] S3. 관리자용 스토리 작성 (매장 인증, 실시간 주문 모니터링, 테이블 관리, 메뉴 관리)
- [x] S4. 각 스토리에 Q3 형식의 인수 조건 작성 (Q7 방식으로 오류/엣지 케이스 반영)
- [x] S5. 스토리 형식(Q2), 우선순위(Q6), 추적성(Q8) 적용
- [x] S6. INVEST 기준 점검 (Independent, Negotiable, Valuable, Estimable, Small, Testable)
- [x] S7. 페르소나와 스토리 매핑 확인
- [x] S8. `stories.md` 저장

### 마무리
- [x] F1. `aidlc-state.md` 및 `audit.md` 갱신
- [ ] F2. 완료 메시지 제시 및 사용자 승인 대기
