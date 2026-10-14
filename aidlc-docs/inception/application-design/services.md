# Services (서비스 정의와 오케스트레이션)

백엔드는 2계층(Router -> Service)이며 서비스가 `sqlite3`로 직접 DB에 접근합니다. 별도 Repository 계층은 없습니다 (Plan Q1: B, Q2: C).

## 서비스 목록과 책임

| 서비스 | 책임 | 사용하는 컴포넌트 |
|---|---|---|
| AuthService | 관리자/테이블 로그인, 로그인 실패 기록과 잠금, 토큰 발급 | Config, Database, Security |
| MenuService | 메뉴 조회/등록/수정/삭제/순서 변경, 입력 검증 | Database, EventBroker |
| TableService | 테이블 등록, 세션 시작/종료, 이력 이관과 조회 | Database, Security, EventBroker |
| OrderService | 주문 생성/조회/상태 전이/삭제, 대시보드 요약 | Database, TableService, MenuService, EventBroker |
| EventBroker | 이벤트 발행/구독 (서비스라기보다 인프라 컴포넌트) | (없음) |

## 서비스 간 규칙
- OrderService만 TableService의 `get_or_start_session`을 호출한다. 세션 시작과 주문 저장은 **같은 트랜잭션**에서 수행한다.
- 이벤트는 **트랜잭션 커밋 이후에만** 발행한다 (롤백된 변경이 대시보드에 보이지 않도록).
- 서비스는 HTTP 개념(상태코드, 헤더)을 알지 못한다. 도메인 예외만 던지고 라우터가 변환한다.
- 연결은 요청 단위로 생성하고 서비스 메서드에 전달하거나 서비스 내부에서 획득한다 (상세는 Functional Design).

## 오케스트레이션 흐름

### 1. 테이블 자동 로그인 (US-C1.1, US-E3)
1. 고객 UI 시작 시 `TableAuthProvider`가 localStorage의 자격 증명으로 `POST /api/customer/auth/login` 호출
2. `AuthService.login_table`이 매장ID, 테이블 번호, 비밀번호 해시 검증
3. 성공: table 토큰(16시간) 반환 -> 메뉴 화면. 실패: 설정 화면(needs_setup)
4. 토큰 만료(401) 시 같은 로그인을 조용히 재시도

### 2. 주문 생성 (US-C4.1, US-C4.2, US-E1, US-E2)
1. 고객 UI: 장바구니 -> 최종 확인 -> `POST /api/customer/orders` (menuId, quantity 목록)
2. `OrderService.create_order`:
   - 트랜잭션 시작
   - 메뉴 ID 존재 여부 확인 (없으면 오류, 어떤 메뉴인지 포함)
   - 서버 저장 가격으로 단가/합계 재계산 (클라이언트 금액이 다르면 안내 정보 포함)
   - `TableService.get_or_start_session`으로 활성 세션 확보 (없으면 생성)
   - 주문 및 주문 항목 저장
   - 커밋
3. 커밋 후 `EventBroker.publish(order_created)`
4. 응답: 주문 번호 -> 고객 UI가 5초 후 메뉴로 이동, 장바구니 비움. 오류 시 장바구니 유지

### 3. 관리자 실시간 모니터링 (US-A2.1, US-A2.2, US-E6)
1. 관리자 UI: `GET /api/admin/dashboard`로 초기 스냅샷 로드
2. `GET /api/admin/events` (SSE) 연결, 이벤트 수신 시 대시보드 쿼리 무효화 -> 재조회
3. 연결이 끊기면 `useEventStream`이 재연결, 재연결 직후 재조회로 놓친 변경분 반영
4. 신규 주문(order_created)은 해당 카드를 강조 표시

### 4. 주문 상태 변경 (US-A2.4, US-E5)
1. `PATCH /api/admin/orders/{id}/status`
2. `OrderService.change_status`: 현재 상태 조회 -> 허용 전이(대기중 -> 준비중 -> 완료)인지 확인 -> 갱신 -> 커밋 -> `order_status_changed` 발행
3. 허용되지 않으면 409. 고객 UI는 폴링으로 새 상태 반영

### 5. 주문 삭제 (US-A3.2, US-E8)
1. 관리자 UI 확인 팝업 후 `DELETE /api/admin/orders/{id}`
2. `OrderService.delete_order`: 트랜잭션에서 주문과 항목 삭제 -> 테이블 합계 재계산 -> 커밋 -> `order_deleted` 발행
3. 응답으로 갱신된 테이블 요약 반환

### 6. 테이블 이용 완료 (US-A3.3, US-E8)
1. 확인 팝업 후 `POST /api/admin/tables/{id}/end-session`
2. `TableService.end_session`: 트랜잭션에서 활성 세션의 주문을 과거 이력(OrderHistory)으로 이관, 세션 종료 시각 기록, 현재 주문 목록/합계 0 -> 커밋 -> `session_ended` 발행
3. 활성 세션이 없거나 이미 종료된 경우 409
4. 이후 같은 테이블의 첫 주문이 새 세션을 만든다

### 7. 관리자 로그인과 잠금 (US-A1.1, US-E4)
1. `POST /api/admin/auth/login`
2. `AuthService.login_admin`: 잠금 상태 확인 (잠겼으면 429 + 남은 시간) -> 매장ID/사용자명/bcrypt 검증 -> 실패면 횟수 기록(5회 도달 시 15분 잠금) -> 성공이면 횟수 초기화, 16시간 JWT 발급
3. 잠금 상태 저장 위치는 Functional Design에서 확정 (SQLite 테이블 사용 예정)

### 8. 메뉴 관리 (US-A4.x, US-E7)
1. 관리자 UI 폼 -> 메뉴 API 호출
2. `MenuService`가 필수 필드와 가격 범위를 검증하고 저장, 실패 시 필드별 오류(422)
3. 저장 후 `menu_changed` 이벤트 발행 (관리자 화면 동기화용). 고객 화면은 메뉴 조회 시 최신 데이터를 사용

## 동시성 및 일관성 메모
- SQLite는 WAL 모드, 짧은 트랜잭션, 요청 단위 연결을 사용한다 (소규모 단일 서버 전제).
- EventBroker.publish는 스레드풀에서 호출되므로 이벤트 루프로 안전하게 전달한다 (`loop.call_soon_threadsafe`).
- 순차 상태 전이는 `UPDATE ... WHERE id=? AND status=?` 같은 조건부 갱신으로 경합을 방지한다 (상세는 Functional Design).
