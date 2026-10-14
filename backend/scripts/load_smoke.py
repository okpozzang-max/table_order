"""가벼운 부하 확인 스크립트 (개발용, 운영 서버에는 사용하지 않는다).

실행 중인 서버에 여러 테이블이 동시에 주문하고, 관리자 SSE 구독자들이 이벤트를 받는 상황을 만들어
주문 응답 시간, 오류 수, 이벤트 전달 지연을 출력한다. 테이블 1..N을 (없으면) 등록한다.

사용: python scripts/load_smoke.py http://127.0.0.1:8000 [--tables 20] [--orders 10] [--subscribers 5]
기본 자격 증명은 .env.example 기준(demo / admin / admin1234, 테이블 비밀번호 1234). 환경변수로 바꿀 수 있다:
LOAD_STORE_ID, LOAD_ADMIN_USER, LOAD_ADMIN_PASSWORD
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
import uuid

import httpx

TABLE_PASSWORD = "1234"


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("base_url")
    parser.add_argument("--tables", type=int, default=20)
    parser.add_argument("--orders", type=int, default=10, help="테이블당 주문 수")
    parser.add_argument("--subscribers", type=int, default=5, help="관리자 SSE 구독자 수")
    args = parser.parse_args()

    store = os.environ.get("LOAD_STORE_ID", "demo")
    http = httpx.Client(base_url=args.base_url, timeout=30)
    res = http.post(
        "/api/admin/auth/login",
        json={
            "storeId": store,
            "username": os.environ.get("LOAD_ADMIN_USER", "admin"),
            "password": os.environ.get("LOAD_ADMIN_PASSWORD", "admin1234"),
        },
    )
    if res.status_code != 200:
        print("관리자 로그인 실패:", res.status_code)
        return 2
    admin = {"Authorization": f"Bearer {res.json()['accessToken']}"}
    for number in range(1, args.tables + 1):
        http.post("/api/admin/tables", json={"tableNumber": number, "password": TABLE_PASSWORD}, headers=admin)  # 중복(409)은 무시

    # ----- SSE 구독자 -----
    received: list[dict[int, float]] = [{} for _ in range(args.subscribers)]
    ready = [threading.Event() for _ in range(args.subscribers)]
    stop = threading.Event()

    def subscribe(index: int) -> None:
        try:
            with httpx.Client(timeout=httpx.Timeout(30, read=None)) as sc:
                with sc.stream("GET", args.base_url + "/api/admin/events", headers=admin) as resp:
                    event = None
                    for line in resp.iter_lines():
                        if line.startswith(": connected"):
                            ready[index].set()
                        elif line.startswith("event: "):
                            event = line[7:]
                        elif line.startswith("data: ") and event == "order_created":
                            received[index][json.loads(line[6:])["payload"]["orderId"]] = time.perf_counter()
                        if stop.is_set():
                            break
        except Exception:  # noqa: BLE001
            ready[index].set()

    threads = [threading.Thread(target=subscribe, args=(i,), daemon=True) for i in range(args.subscribers)]
    [t.start() for t in threads]
    if not all(e.wait(10) for e in ready):
        print("SSE 연결 실패")
        return 2

    # ----- 테이블별 동시 주문 -----
    latencies: list[float] = []
    errors: dict[str, int] = {}
    completed_at: dict[int, float] = {}
    lock = threading.Lock()
    barrier = threading.Barrier(args.tables)

    def table_worker(number: int) -> None:
        with httpx.Client(base_url=args.base_url, timeout=30) as c:
            login = c.post("/api/customer/auth/login", json={"storeId": store, "tableNumber": number, "password": TABLE_PASSWORD})
            headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
            menu = c.get("/api/customer/menus", headers=headers).json()[0]["menus"][0]
            barrier.wait()
            for _ in range(args.orders):
                body = {
                    "clientOrderId": str(uuid.uuid4()),
                    "items": [{"menuId": menu["id"], "quantity": 1}],
                    "clientTotal": menu["price"],
                }
                start = time.perf_counter()
                r = c.post("/api/customer/orders", json=body, headers=headers)
                end = time.perf_counter()
                with lock:
                    latencies.append((end - start) * 1000)
                    if r.status_code == 201:
                        completed_at[r.json()["id"]] = end
                    else:
                        errors[str(r.status_code)] = errors.get(str(r.status_code), 0) + 1

    workers = [threading.Thread(target=table_worker, args=(n,)) for n in range(1, args.tables + 1)]
    wall = time.perf_counter()
    [t.start() for t in workers]
    [t.join() for t in workers]
    wall = time.perf_counter() - wall
    time.sleep(1.5)  # 마지막 이벤트가 도착할 시간
    stop.set()

    total = len(completed_at)
    lags = []
    missing = 0
    for sub in received:
        for order_id, done in completed_at.items():
            if order_id in sub:
                lags.append(max(0.0, sub[order_id] - done) * 1000)
            else:
                missing += 1
    print(f"주문 {args.tables}테이블 x {args.orders}건 = {args.tables * args.orders}건 요청, 성공(201) {total}건, 소요 {wall:.2f}초, {total / wall:.1f}건/초")
    print(f"주문 응답 시간(ms): p50={statistics.median(latencies):.0f} p95={percentile(latencies, 95):.0f} max={max(latencies):.0f}")
    print(f"오류: {errors or '없음'}")
    print(f"SSE 구독자 {args.subscribers}명: 이벤트 누락 {missing}건 (기대 {total * args.subscribers}건 중), "
          f"전달 지연(ms, 응답 완료 후) p95={percentile(lags, 95):.0f} max={max(lags) if lags else 0:.0f}")
    ok = not errors and missing == 0 and total == args.tables * args.orders
    print("결과:", "통과" if ok else "확인 필요")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
