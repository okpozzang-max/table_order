# Unit Test Execution

단위 테스트는 각 Unit의 Code Generation 단계에서 함께 생성되었습니다. 이 문서는 전체 실행 방법과 기대 결과입니다.

## 백엔드 (pytest)

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest                       # 전체: 단위 + API + 계약 + 통합 (약 1~2분)
pytest tests/unit            # 서비스/보안/DB/설정/시드/이벤트 브로커/검증 (빠름)
pytest tests/unit/test_order_service.py -k Concurrent   # 특정 테스트만
```

기대 결과 (검증 환경): **522 passed, 0 failed**.

| 영역 | 개수 | 주요 내용 |
|---|---|---|
| `tests/unit` | 276 | 설정/오류/검증, 스키마 제약(core, order), 보안(bcrypt/JWT), AuthService(잠금), MenuService, EventBroker/SSE 프레임, TableService(이용 완료 이관, 롤백, 날짜 경계), OrderService(멱등, 가격 재계산, 전이 표 9칸, 동시성 경쟁), 시드 |
| `tests/api` | 105 | 인증/메뉴/오류/정적 서빙, 주문·대시보드·상태·삭제·테이블·과거 내역 HTTP, SSE(실제 서버) |
| `tests/contract` | 140 | `contracts/openapi.yaml` 과 구현 일치 (19 operation x 7항목, 실제 응답 필수 필드, 오류 본문) |
| `tests/integration` | 1 | 주문부터 이용 완료까지 전체 시나리오 (실제 서버) |

- 가장 오래 걸리는 테스트는 SSE 종료/keep-alive 관련 (각 1~4초).
- 커버리지 측정 도구는 설정하지 않았습니다 (MVP). 요구 항목별 테스트 위치는 각 Unit의 `code/code-summary.md` 스토리 표에 있습니다.
- 테스트는 시각을 주입 가능한 `FakeClock` 으로 다루므로 16시간 토큰 만료, 잠금 시간, 한국 시간 자정 경계를 실제로 기다리지 않고 검증합니다.

## 프론트엔드 (vitest)

```powershell
cd frontend
npx tsc --noEmit             # 타입 검사 (계약에서 생성한 타입 포함)
npx vitest run               # 컴포넌트/유틸/가짜 API 테스트
```

기대 결과: `tsc` 오류 0, **25 files / 166 tests passed**. 프론트엔드 테스트는 가짜 API(인-메모리)를 사용하며 백엔드가 필요 없습니다.

## 결과 확인과 실패 대응

1. 요약 줄(`522 passed`)과 `FAILED` 목록을 확인합니다. 임시 파일은 `backend/.pytest_tmp` 입니다.
2. 실패 시 `pytest <경로>::<테스트이름> -x --tb=short` 로 하나씩 재현합니다.
3. 계약 일치 테스트(`tests/contract`)가 실패하면 `contracts/openapi.yaml` 과 라우터의 상태 코드/파라미터/스키마가 어긋난 것입니다. 계약을 고쳤다면 프론트엔드에서 `npm run gen:api` 후 `tsc` 를 다시 확인합니다.
4. SSE/통합 테스트가 간헐적으로 느리거나 실패하면 포트 충돌(방화벽/백신)과 PC 부하를 먼저 확인합니다. 테스트는 임의의 빈 포트(127.0.0.1)만 사용합니다.
