# Integration Test Instructions

## Purpose

Unit 간 연결을 확인합니다: `frontend` -> (HTTP/SSE, 계약) -> `backend-core`(인증, 메뉴) + `backend-order`(테이블, 주문, 이벤트). 배포 형태는 하나의 FastAPI 프로세스이므로 별도 서비스 기동 없이 실행됩니다.

## 자동화된 통합 검증 (백엔드)

| 시나리오 | 위치 | 확인 내용 |
|---|---|---|
| core <-> order: 메뉴 → 주문 | `tests/api/test_orders_api.py`, `tests/unit/test_order_service.py` | 삭제된 메뉴는 `MENU_UNAVAILABLE`, 가격 변경은 `PRICE_CHANGED`, 기존 주문은 메뉴 변경 후에도 스냅샷 유지, 이름 재사용 시 새 ID |
| core <-> order: 테이블 등록 → 로그인 | `tests/api/test_tables_api.py` | 등록 직후 같은 번호/비밀번호로 `customerLogin` 성공 |
| core → order: 메뉴 변경 이벤트 | `tests/api/test_sse_api.py::test_full_lifecycle_events_in_order` | `MenuService` 변경이 `menu_changed` 로 SSE에 도달 |
| 서비스 ↔ SSE | `tests/api/test_sse_api.py` (실제 uvicorn) | 신규 주문 2초 이내 수신, 모든 구독자 팬아웃, keep-alive, 토큰 만료 시 종료, 연결 종료 시 구독 해제, 서버 종료 |
| 계약 ↔ 구현 (frontend ↔ backend) | `tests/contract/test_contract.py` | 19개 operation의 경로/메서드/상태 코드/보안/요청·응답 모양/파라미터/오류 본문 |
| 전체 흐름 | `tests/integration/test_scenario.py` | 아래 시나리오 1~9를 실제 HTTP + SSE로 수행 |

```powershell
cd backend
pytest tests/integration tests/api/test_sse_api.py tests/contract
```

기대: 모두 통과 (SSE/통합 테스트는 임의의 빈 포트에 서버를 띄우고 종료 시 정리합니다).

### 통합 시나리오 (`test_full_day_scenario`)

1. 관리자 로그인, 대시보드(테이블 5개, 주문 없음), SSE 연결
2. 테이블 6 등록 → 목록에 `sessionActive=false`, 즉시 태블릿 로그인
3. 고객 테이블 1: 로그인 → 메뉴 조회 → 주문 (201, 주문 번호)
4. 관리자 SSE에 `order_created` 도달, 대시보드 합계 반영
5. 상태 변경 (건너뛰기는 409, 준비 시작 → 완료, 이벤트 수신), 고객 내역에 반영
6. 같은 `clientOrderId` 재전송 → 200, 주문 1건 유지, 이벤트 없음
7. 메뉴 가격 수정 → 이전 가격은 `PRICE_CHANGED`(현재 가격 포함), 새 가격으로 성공
8. 주문 삭제(합계 재계산), 이용 완료(합계 0, 고객 내역 비움, 과거 내역 이동, 한국 시간 날짜 필터), 중복 이용 완료 `NO_ACTIVE_SESSION`
9. 이용 완료 후 새 주문 → 새 세션 ID

## 프론트엔드 real 모드와의 연동 확인 (수동)

자동화된 브라우저 테스트는 범위에서 제외했습니다 (frontend 계획 결정). 같은 요청이 백엔드 수준에서 검증되었고, 화면 동작은 `e2e-test-instructions.md` 의 수동 절차로 확인합니다.

## 실제 프로세스 스모크 (선택)

서버를 실제 프로세스로 띄워 확인하려면:

```powershell
cd backend
python scripts/seed.py
python -m uvicorn app.main:create_app --factory --port 8000 --timeout-graceful-shutdown 5
# 다른 터미널
python scripts/load_smoke.py http://127.0.0.1:8000 --tables 5 --orders 3 --subscribers 2
```

`load_smoke.py` 는 여러 테이블이 동시에 주문하고 관리자 SSE 구독자가 이벤트를 받는 흐름을 실행해 오류/누락/지연을 출력합니다 (자세한 내용은 `performance-test-instructions.md`).

## Cleanup

- 자동 테스트는 임시 DB(`backend/.pytest_tmp`)를 쓰며 따로 정리할 것이 없습니다.
- 수동 스모크에서 만든 DB를 지우려면 서버를 종료한 뒤 `DB_PATH` 파일(`backend/data/table_order.sqlite3`)을 삭제하거나 `python scripts/seed.py --reset --yes` 를 실행합니다 (개발 데이터 전체 삭제 주의).
