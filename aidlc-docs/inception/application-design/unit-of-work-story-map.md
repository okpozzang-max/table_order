# Unit of Work - Story Map (스토리 -> Unit 매핑)

모든 스토리는 UI가 있으므로 `frontend`를 포함합니다. 표의 "백엔드 Unit"은 해당 스토리를 서버에서 구현하는 Unit입니다. 서버 로직이 없는 스토리는 `-`로 표기합니다.

## 고객 (P1)

| 스토리 | 제목 | frontend | 백엔드 Unit | 비고 |
|---|---|---|---|---|
| US-C1.1 | 저장된 정보로 자동 로그인 | ● | backend-core | AuthService.login_table (테이블은 시드로 준비) |
| US-C2.1 | 카테고리별 메뉴 탐색 | ● | backend-core | MenuService.list_menus_grouped |
| US-C2.2 | 메뉴 상세 정보 확인 | ● | backend-core | |
| US-C3.1 | 장바구니 담기/삭제 | ● | - | 클라이언트 전용 |
| US-C3.2 | 수량 조절, 총 금액 | ● | - | 클라이언트 전용 |
| US-C3.3 | 장바구니 유지/비우기 | ● | - | localStorage |
| US-C4.1 | 주문 확인 후 확정 | ● | backend-order | OrderService.create_order |
| US-C4.2 | 주문 성공 확인, 메뉴 복귀 | ● | backend-order | |
| US-C5.1 | 현재 세션 주문 내역 | ● | backend-order | |
| US-C5.2 | 주문 상태 자동 갱신 | ● | backend-order | 폴링 |

## 관리자 (P2)

| 스토리 | 제목 | frontend | 백엔드 Unit | 비고 |
|---|---|---|---|---|
| US-A1.1 | 매장 로그인 | ● | backend-core | AuthService.login_admin |
| US-A1.2 | 16시간 세션 유지 | ● | backend-core | JWT TTL |
| US-A2.1 | 테이블별 대시보드 | ● | backend-order | dashboard_snapshot |
| US-A2.2 | 신규 주문 실시간 수신/강조 | ● | backend-order | EventBroker, SSE |
| US-A2.3 | 주문 상세 보기 | ● | backend-order | |
| US-A2.4 | 주문 상태 변경 | ● | backend-order | |
| US-A2.5 | 테이블별 필터링 | ● | backend-order | |
| US-A3.1 | 테이블 태블릿 초기 설정 | ● | backend-order | 등록 API는 backend-order, 로그인 검증은 backend-core |
| US-A3.2 | 주문 삭제 | ● | backend-order | |
| US-A3.3 | 이용 완료 처리 (세션 종료) | ● | backend-order | |
| US-A3.4 | 과거 주문 내역 조회 | ● | backend-order | |
| US-A4.1 | 메뉴 목록 조회 | ● | backend-core | |
| US-A4.2 | 메뉴 등록 | ● | backend-core | |
| US-A4.3 | 메뉴 수정/삭제 | ● | backend-core | |
| US-A4.4 | 노출 순서 조정 | ● | backend-core | |

## 오류/예외 (EP-E)

| 스토리 | 제목 | frontend | 백엔드 Unit | 비고 |
|---|---|---|---|---|
| US-E1 | 주문 실패 시 장바구니 유지 | ● | backend-order | |
| US-E2 | 존재하지 않는 메뉴 주문 처리 | ● | backend-order | 메뉴 조회는 core의 MenuService 사용 |
| US-E3 | 테이블 로그인 실패 처리 | ● | backend-core | |
| US-E4 | 관리자 로그인 실패/잠금 | ● | backend-core | |
| US-E5 | 잘못된 상태 전이 거부 | ● | backend-order | |
| US-E6 | 실시간 연결 오류 복구 | ● | backend-order | SSE keep-alive, 폴링 재시도는 프론트엔드 |
| US-E7 | 메뉴 입력 검증 실패 안내 | ● | backend-core | |
| US-E8 | 삭제/이용 완료 실패 피드백 | ● | backend-order | 트랜잭션 |
| US-E9 | 관리자 세션 만료 후 재인증 | ● | backend-core | Deps 401 |

## 집계

| Unit | 담당 스토리 수 | 스토리 |
|---|---|---|
| frontend | 34 (전체의 UI 부분) | 모든 스토리 |
| backend-core | 13 | US-C1.1, C2.1, C2.2, A1.1, A1.2, A4.1~A4.4, E3, E4, E7, E9 |
| backend-order | 18 | US-C4.1, C4.2, C5.1, C5.2, A2.1~A2.5, A3.1~A3.4, E1, E2, E5, E6, E8 |
| 서버 로직 없음 (frontend 전용) | 3 | US-C3.1, C3.2, C3.3 |

검증: 13 + 18 + 3 = 34. 모든 스토리가 최소 하나의 Unit에 할당되었고, 중복 할당된 백엔드 스토리는 없다.
