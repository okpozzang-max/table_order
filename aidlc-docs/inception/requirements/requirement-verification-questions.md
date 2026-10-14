# 요구사항 확인 질문 (Requirement Verification Questions)

`requirements/table-order-requirements.md` 와 `requirements/constraints.md` 를 분석한 결과, 요구사항은 대부분 명확하지만 아래 항목은 구현 전에 확정이 필요합니다.
각 질문의 `[Answer]:` 뒤에 선택지 알파벳을 적어주세요. 맞는 선택지가 없으면 마지막 `X) Other` 를 선택하고 설명을 적어주세요.

---

## Part 1. 기술 스택 / 배포

## Question 1
백엔드 기술 스택은 무엇을 사용할까요?

A) Node.js + Express (TypeScript)

B) Python + FastAPI

C) Java + Spring Boot

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 2
프론트엔드(고객용/관리자용 웹UI) 기술 스택은 무엇을 사용할까요?

A) React (TypeScript, Vite)

B) Vue 3 (TypeScript, Vite)

C) Next.js

D) 순수 HTML/JavaScript (프레임워크 없음)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
데이터 저장소는 무엇을 사용할까요?

A) PostgreSQL

B) MySQL

C) Amazon DynamoDB

D) SQLite (로컬/개발 중심, 단순 구성)

X) Other (please describe after [Answer]: tag below)

[Answer]: D

## Question 4
배포 대상/실행 환경은 어디를 목표로 하나요?

A) 로컬 실행 (docker-compose 등)만 지원

B) AWS 클라우드 배포까지 포함 (예: ECS/Fargate 또는 Lambda + RDS 등, IaC 포함)

C) 로컬 실행 우선 구현 후 AWS 배포는 추후 별도 진행

X) Other (please describe after [Answer]: tag below)

[Answer]: A - MVP는 로컬 배포만 수행, docker 사용 하지 않음

---

## Part 2. 기능 범위 및 정책

## Question 5
시스템이 지원할 매장 수는 어떻게 되나요? (요구사항에 "매장 식별자"가 있어 멀티 매장 여부 확인 필요)

A) 단일 매장 전용 (매장 식별자는 입력받지만 데이터는 1개 매장 기준)

B) 멀티 매장(멀티 테넌트) - 매장별로 데이터가 완전히 분리되어야 함

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
예상 규모(매장당 테이블 수 및 동시 접속)는 어느 정도인가요?

A) 소규모: 매장당 ~20개 테이블

B) 중규모: 매장당 20~100개 테이블

C) 대규모: 매장당 100개 이상 또는 다수 매장 동시 운영

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
매장 및 관리자 계정은 어떻게 생성하나요? (요구사항에 회원가입/직원 관리 기능은 없음)

A) 시드 스크립트/CLI로 사전 생성 (회원가입 화면 없음)

B) 관리자 회원가입 API/화면 제공

C) 매장당 관리자 1개 계정만 환경설정(설정 파일/환경변수)으로 지정

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 8
메뉴 이미지는 어떻게 처리하나요? (constraints.md에서 이미지 리사이징/최적화는 제외됨)

A) 외부 이미지 URL 문자열만 저장 (파일 업로드 없음)

B) 관리자가 이미지 파일 업로드 (리사이징 없이 원본 저장, 예: S3 또는 로컬 디스크)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9
메뉴 카테고리는 어떻게 관리하나요?

A) 메뉴 등록 시 카테고리 이름을 문자열로 입력 (별도 카테고리 CRUD 없음)

B) 카테고리를 별도로 등록/수정/삭제하는 관리 기능 제공

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10
주문 상태(대기중/준비중/완료) 변경 규칙은 어떻게 하나요?

A) 순차 변경만 허용 (대기중 → 준비중 → 완료)

B) 관리자가 임의의 상태로 자유롭게 변경 가능

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11
고객 화면의 주문 상태 실시간 업데이트(요구사항상 "선택사항")는 어떻게 할까요?

A) MVP에 포함 - SSE로 실시간 반영

B) MVP에 포함 - 주기적 폴링(예: 5~10초)으로 반영

C) MVP에서 제외 (화면 진입/새로고침 시에만 최신 상태 조회)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 12
관리자 로그인 시도 제한 정책은 어떻게 할까요?

A) 연속 5회 실패 시 15분 잠금

B) 연속 3회 실패 시 30분 잠금

C) 정책 수치는 AI가 합리적으로 정해도 됨

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 13
UI 언어는 어떻게 하나요? (다국어 기능은 제외 항목)

A) 한국어 단일 언어

B) 영어 단일 언어

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Part 3. 확장 기능(Extension) 적용 여부 - 확장 기능 사용 계획 없음

## Question 14: Security Extensions
Should security extension rules be enforced for this project?

A) Yes — enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)

B) No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 15: Resiliency Extensions
Should the resiliency baseline be applied to this project?

**What this extension is.** Enabling it applies a set of **directional, design-time best practices** for building resilient systems, derived from the **AWS Well-Architected Framework (Reliability Pillar)** and resilience-review guidance. It steers requirements, design, and code toward fault tolerance, high availability, observability, and recoverability — covering 15 practice areas across business goals, change management, observability, high availability, disaster recovery, and continuous improvement.

**What this extension is NOT.** Enabling it does **not** make your workload production-ready, nor does it certify or guarantee any availability, RTO, or RPO target. It is a **starting point** that scaffolds good resiliency decisions early — it is not a substitute for a formal **AWS Well-Architected Review** of the built system.

Treat the output as a well-grounded **first draft of your resiliency posture** to build on and validate — not a finished, production-certified result.

A) Yes — apply the resiliency baseline as directional best practices and design-time guidance (recommended for business-critical workloads, as an informed starting point that you can validate and harden before go-live)

B) No — skip the resiliency baseline (suitable for PoCs, prototypes, and experimental projects where rapid iteration matters more than reliability)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 16: Property-Based Testing Extension
Should property-based testing (PBT) rules be enforced for this project?

A) Yes — enforce all PBT rules as blocking constraints (recommended for projects with business logic, data transformations, serialization, or stateful components)

B) Partial — enforce PBT rules only for pure functions and serialization round-trips (suitable for projects with limited algorithmic complexity)

C) No — skip all PBT rules (suitable for simple CRUD applications, UI-only projects, or thin integration layers with no significant business logic)

X) Other (please describe after [Answer]: tag below)

[Answer]: 
