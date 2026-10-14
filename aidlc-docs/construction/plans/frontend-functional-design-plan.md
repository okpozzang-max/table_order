# Functional Design 계획 - frontend (Unit 1)

CONSTRUCTION 단계 시작. 대상 Unit: `frontend` (고객용 + 관리자용 단일 React 앱, 가짜 API로 독립 개발).
참고: `unit-of-work.md`, `unit-of-work-story-map.md`, `stories.md`(34개 스토리), `components.md`, `component-methods.md`

이 단계에서는 화면 흐름, 컴포넌트 구조와 상태, 폼 검증, 오류 표시 규칙, 클라이언트 데이터 모델을 상세 설계합니다. 서버 스키마와 서버 업무 규칙은 backend Unit의 Functional Design에서 다룹니다.

아래 질문의 `[Answer]:` 뒤에 알파벳을 적어주세요. 맞는 선택지가 없으면 `X) Other`를 고르고 설명을 적어주세요. "추천해서 진행"을 원하시면 그렇게 적어주셔도 됩니다.

---

## Part A. 질문

### 고객 화면

## Question 1
장바구니에서 같은 메뉴의 최대 수량은 얼마로 할까요?

A) 99개

B) 20개

C) 제한 없음

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 2
고객 메뉴 화면의 카테고리 이동 UI는 어떻게 할까요? (태블릿 가로 화면 기준)

A) 화면 상단의 가로 탭 (선택한 카테고리로 목록 이동)

B) 화면 좌측 세로 사이드바

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 3
장바구니 표시 방식은 어떻게 할까요?

A) 메뉴 화면 오른쪽에 항상 보이는 고정 패널 (태블릿 가로 기준)

B) 화면 하단 요약 바(개수, 합계) + 누르면 올라오는 장바구니 드로어

C) 별도 장바구니 페이지

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
주문 성공 화면(5초 후 메뉴로 자동 이동)은 어떻게 보여줄까요?

A) 주문 번호 + 남은 초 카운트다운 + "바로 메뉴로 이동" 버튼

B) 주문 번호 + 안내 문구만 (카운트다운, 버튼 없음)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
고객 주문 내역의 상태 폴링 주기는 얼마로 할까요? (요구사항: 5~10초)

A) 5초

B) 10초

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
주문 내역 목록이 길어질 때 표시 방식은 어떻게 할까요? (요구사항: 페이지네이션 또는 무한 스크롤)

A) "더 보기" 버튼으로 다음 페이지 추가 (한 번에 10건)

B) 스크롤 끝에서 자동으로 다음 페이지 로드 (무한 스크롤, 한 번에 10건)

C) 페이지 번호 방식 (한 페이지 10건)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

### 관리자 화면

## Question 7
대시보드 테이블 카드에 보여줄 "최신 주문 미리보기" 개수(n)는 몇 개로 할까요?

A) 3개

B) 5개

X) Other (please describe after [Answer]: tag below)

[Answer]:A 

## Question 8
신규 주문의 시각적 강조는 언제까지 유지할까요?

A) 10초 후 자동 해제

B) 관리자가 해당 카드를 열어 확인(클릭)할 때까지 유지

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 9
대시보드 테이블 카드의 정렬 방식은 어떻게 할까요?

A) 테이블 번호 오름차순 고정

B) 최근 주문이 있는 테이블을 앞으로 (주문 없는 테이블은 번호순 뒤쪽)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10
관리자 메뉴 노출 순서 조정 UI는 어떻게 할까요?

A) 각 메뉴 행의 위/아래 이동 버튼

B) 드래그 앤 드롭

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11
관리자 로그인 토큰(JWT)은 브라우저 어디에 보관할까요? (요구사항: 새로고침해도 16시간 유지)

A) localStorage (브라우저를 닫았다 열어도 만료 전까지 유지)

B) sessionStorage (새로고침은 유지, 탭/브라우저를 닫으면 로그아웃)

X) Other (please describe after [Answer]: tag below)

[Answer]: 너가 추천하고 그 사항으로 진행해

### 입력 검증 (프론트 폼 + 이후 백엔드와 공통 적용)

## Question 12
메뉴 등록/수정 폼의 검증 값은 어떻게 할까요?

A) 메뉴명 1~50자 필수, 설명 0~300자 (선택), 카테고리 1~30자 필수, 가격 100~1,000,000원 정수, 이미지 URL은 선택이며 입력 시 http/https 형식

B) 메뉴명 1~100자 필수, 설명 0~500자 (선택), 카테고리 1~50자 필수, 가격 1~10,000,000원 정수, 이미지 URL은 선택이며 입력 시 http/https 형식

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 13
테이블 비밀번호 정책(관리자가 테이블 등록 시 설정)은 어떻게 할까요?

A) 숫자 4자리

B) 영문/숫자 6자 이상

C) 4자 이상, 형식 제한 없음

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### 기술 선택

## Question 14
UI 스타일링은 어떤 방식으로 할까요?

A) Tailwind CSS

B) CSS Modules (직접 작성, 추가 UI 라이브러리 없음)

C) MUI (Material UI) 같은 컴포넌트 라이브러리

X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Part B. 별도 질문 없이 적용할 설계 가정 (이견이 있으면 알려주세요)

| # | 가정 |
|---|---|
| G1 | 같은 메뉴를 다시 담으면 새 항목이 아니라 기존 항목의 수량이 1 증가한다. |
| G2 | 수량 1에서 감소하면 항목이 제거된다 (US-C3.2). |
| G3 | 상단 내비게이션에 "메뉴" / "주문 내역" 두 탭을 두고, 메뉴 화면이 기본이다. |
| G4 | 주문 상태 변경은 카드/상세의 단일 "다음 단계" 버튼으로 한다 (대기중 -> "준비 시작", 준비중 -> "완료 처리", 완료는 버튼 없음). |
| G5 | 과거 내역의 날짜 필터는 시작일~종료일 두 개의 date 입력이다. |
| G6 | 대시보드 테이블 필터는 드롭다운(전체 / 테이블 N)이다. |
| G7 | 라우팅은 react-router, API 타입은 `openapi-typescript`로 `contracts/openapi.yaml`에서 생성한다. |
| G8 | 가짜 API는 샘플 메뉴/테이블 데이터와 약간의 응답 지연, 계약상의 오류 응답(401/409/422/429)을 재현한다. |
| G9 | 금액은 원 단위 정수, 화면에는 `12,000원` 형식으로 표시한다. |
| G10 | 한국어 단일 UI, 날짜/시간은 `YYYY-MM-DD HH:mm` 표시(브라우저 로컬 시간). |
| G11 | 서버 오류 메시지는 계약의 오류 코드를 사용자용 한국어 문구로 변환해 표시한다. |

---

## Part C. 실행 체크리스트 (답변 확정 후 수행)

### 분석
- [x] A1. unit-of-work.md, 스토리 맵, 스토리 34개 재확인
- [x] A2. 답변 분석 및 모호성 해소 (Q11은 "추천해서 진행" 위임 -> localStorage 확정, 근거는 business-rules.md. 충돌/모호성 없음)

### 산출물 생성 (`aidlc-docs/construction/frontend/functional-design/`)
- [x] D1. `domain-entities.md`: 클라이언트 데이터 모델(API DTO 형태, CartItem, 로컬 저장 스키마, 상태 enum)
- [x] D2. `business-logic-model.md`: 화면 흐름, 상태 전이, 자동 로그인/재로그인, 장바구니 계산, 폴링/SSE 처리 흐름
- [x] D3. `business-rules.md`: 폼 검증, 수량/금액 규칙, 오류 코드 -> 문구 매핑, 강조/폴링 규칙
- [x] D4. `frontend-components.md`: 컴포넌트 계층, props/state, 상호작용 흐름, API 연동 지점
- [x] D5. 모든 프론트엔드 관련 스토리(34개)가 설계에 반영되었는지 검증

### 마무리
- [x] F1. `aidlc-state.md`, `audit.md` 갱신
- [ ] F2. 완료 메시지 제시 및 사용자 승인 대기
