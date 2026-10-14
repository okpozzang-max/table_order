# Unit of Work Dependency (Unit 간 의존성)

## 의존성 매트릭스

행이 열에 **의존**하면 `●`. 구분: 코드 의존 / 계약 의존 / 런타임 통합.

| 의존하는 Unit \ 대상 | frontend | backend-core | backend-order | contracts/openapi.yaml |
|---|---|---|---|---|
| frontend | - | 없음 (가짜 API로 독립 개발) | 없음 | ● 계약 의존 (타입 생성) |
| backend-core | 없음 | - | 없음 | ● 계약 의존 (구현 + 일치 검증) |
| backend-order | 없음 (통합 시 정적 서빙 대상) | ● 코드 의존 (Config, Database, Security, Deps, AuthService 결과, MenuService) | - | ● 계약 의존 (구현 + 일치 검증) |

- `backend-core`는 `backend-order`에 의존하지 않는다. MenuService의 이벤트 발행기는 선택적 주입(기본 no-op)이며 backend-order가 실제 EventBroker를 연결한다.
- `frontend`는 다른 Unit의 코드를 import하지 않는다. 유일한 접점은 `contracts/openapi.yaml`이다.
- `frontend`와 `backend-*`의 실제 연결은 `backend-order` 완료 후의 통합 단계에서 한다.

## 구현 순서와 근거

| 순서 | Unit | 선행 조건 | 근거 |
|---|---|---|---|
| 1 | frontend | 없음 | 화면과 API 계약을 먼저 확정해 요구사항 이해를 빨리 검증 (Q3: B). 가짜 API로 독립 실행 |
| 2 | backend-core | `contracts/openapi.yaml` (Unit 1 산출) | backend-order의 선행 기반(Config, Database, Security, 인증, 메뉴) |
| 3 | backend-order | backend-core 완료 | TableService/OrderService가 core의 Database, Security, MenuService를 사용 |

```
frontend --(openapi.yaml)--> backend-core --(코드 의존)--> backend-order
    |                                                           |
    +---------------- 통합 (실제 API 연결) <-------------------+
```

텍스트 대안:
1. frontend: 계약 작성 -> 가짜 API 위에서 UI 완성
2. backend-core: 계약의 인증/메뉴 경로 구현
3. backend-order: 계약의 주문/테이블/SSE 경로 구현 -> 프론트엔드 실제 API 연결 및 통합 확인

## 공유 자원과 통합 지점

| 자원 | 소유 Unit | 사용하는 Unit | 비고 |
|---|---|---|---|
| `contracts/openapi.yaml` | frontend (작성) | backend-core, backend-order (구현/검증) | 변경 시 타입 재생성과 백엔드 일치 테스트 갱신 |
| SQLite 스키마 부트스트랩(`db.py`) | backend-core | backend-order | backend-order는 자기 테이블을 스키마 확장 방식으로 추가 |
| `tables` 테이블 | backend-core (스키마) | backend-order (등록/세션 관리) | core 단계에서는 시드로 데이터 생성 |
| Security(JWT/bcrypt), Deps | backend-core | backend-order | 관리자/테이블 인증 의존성 재사용 |
| MenuService | backend-core | backend-order (OrderService가 가격 조회) | |
| EventBroker | backend-order | backend-core (선택적 주입 지점만) | |
| 가짜 API 모듈 | frontend | frontend | 최종 통합 시 실제 ApiClient로 전환 (설정 스위치) |

## 위험과 완화

| 위험 | 완화 |
|---|---|
| 계약과 실제 백엔드 응답 불일치 | 각 backend Unit에 OpenAPI 일치 테스트 포함 |
| 프론트엔드가 가짜 API에 맞춰 과적합 | 가짜 API가 계약의 오류 응답(401/409/422/429)도 재현하도록 작성 |
| 계약 변경 파급 | 변경 시 openapi.yaml만 수정 후 타입 재생성, 프론트/백엔드 테스트로 즉시 감지 |
| 통합 시점이 늦음 | Unit 3 마지막에 통합 시나리오(주문 -> SSE -> 상태 변경 -> 이용 완료)를 테스트로 확정 |
