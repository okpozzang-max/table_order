from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.events import CLOSE_OVERFLOW, EventBroker, format_sse, stream_events
from app.events_port import ServerEvent


def ev(n: int = 1, type_: str = "order_created", table_id: int | None = 1) -> ServerEvent:
    return ServerEvent(type=type_, table_id=table_id, payload={"orderId": n})


def system_now() -> datetime:
    return datetime.now(timezone.utc)


async def next_frame(gen, timeout: float = 2.0) -> str:  # type: ignore[no-untyped-def]
    return await asyncio.wait_for(gen.__anext__(), timeout)


class TestFormat:
    def test_frame_shape(self) -> None:
        frame = format_sse(ev(7))
        assert frame == 'event: order_created\ndata: {"type":"order_created","tableId":1,"payload":{"orderId":7}}\n\n'

    def test_data_is_single_line_json_with_camel_case(self) -> None:
        frame = format_sse(ServerEvent(type="menu_changed", table_id=None, payload={}))
        lines = frame.split("\n")
        assert lines[0] == "event: menu_changed"
        assert lines[1].startswith("data: ") and len(lines) == 4  # event, data, 빈 줄 2개
        assert json.loads(lines[1][6:]) == {"type": "menu_changed", "tableId": None, "payload": {}}

    def test_newlines_inside_payload_stay_on_one_line(self) -> None:
        frame = format_sse(ServerEvent(type="order_created", table_id=1, payload={"note": "a\nb"}))
        assert frame.count("\n") == 3  # event 줄, data 줄, 빈 줄만 줄바꿈이다
        assert "\\n" in frame.split("\n")[1]  # 페이로드의 줄바꿈은 이스케이프된다


class TestBroker:
    def test_publish_without_subscribers_is_noop(self) -> None:
        EventBroker().publish(ev())

    def test_fan_out_to_all_subscribers(self) -> None:
        async def run() -> list[int]:
            broker = EventBroker()
            a, b = broker.subscribe(), broker.subscribe()
            broker.publish(ev(1))
            got = [(await asyncio.wait_for(s.queue.get(), 1)).payload["orderId"] for s in (a, b)]
            return got

        assert asyncio.run(run()) == [1, 1]

    def test_publish_from_other_thread(self) -> None:
        async def run() -> int:
            broker = EventBroker()
            sub = broker.subscribe()
            t = threading.Thread(target=lambda: broker.publish(ev(42)))
            t.start()
            event = await asyncio.wait_for(sub.queue.get(), 2)
            t.join()
            return event.payload["orderId"]

        assert asyncio.run(run()) == 42

    def test_publish_does_not_block_when_subscriber_is_slow(self) -> None:
        async def run() -> float:
            broker = EventBroker(queue_size=2)
            broker.subscribe()
            start = time.perf_counter()
            for i in range(500):
                broker.publish(ev(i))
            elapsed = time.perf_counter() - start
            await asyncio.sleep(0.05)
            return elapsed

        assert asyncio.run(run()) < 1.0

    def test_unsubscribe_stops_delivery(self) -> None:
        async def run() -> int:
            broker = EventBroker()
            sub = broker.subscribe()
            broker.unsubscribe(sub)
            broker.publish(ev())
            await asyncio.sleep(0.05)
            return sub.queue.qsize() + broker.subscriber_count

        assert asyncio.run(run()) == 0

    def test_overflow_disconnects_only_the_slow_subscriber(self) -> None:
        async def run() -> tuple[str | None, int, int]:
            broker = EventBroker(queue_size=3)
            slow, fast = broker.subscribe(), broker.subscribe()
            for i in range(3):  # 둘 다 가득 참
                broker.publish(ev(i))
            await asyncio.sleep(0.05)
            await fast.queue.get()  # 빠른 구독자는 소비해서 자리가 생김
            broker.publish(ev(99))  # slow만 넘침
            await asyncio.sleep(0.05)
            return slow.close_reason, broker.subscriber_count, fast.queue.qsize()

        reason, count, fast_size = asyncio.run(run())
        assert reason == CLOSE_OVERFLOW
        assert count == 1
        assert fast_size == 3  # 남은 2건 + 99

    def test_close_all_signals_every_subscriber(self) -> None:
        async def run() -> list[bool]:
            broker = EventBroker()
            subs = [broker.subscribe(), broker.subscribe()]
            broker.close_all()
            await asyncio.sleep(0.05)
            return [s.close_reason == "shutdown" for s in subs] + [broker.subscriber_count == 0]

        assert asyncio.run(run()) == [True, True, True]

    def test_publish_after_loop_closed_does_not_raise(self) -> None:
        broker = EventBroker()

        async def subscribe_and_leave() -> None:
            broker.subscribe()

        asyncio.run(subscribe_and_leave())  # 루프가 닫힌 뒤에도 구독이 남아 있다
        broker.publish(ev())  # RuntimeError가 밖으로 나오면 안 된다
        assert broker.subscriber_count == 0


class TestStream:
    def test_connected_then_events_then_unsubscribe_on_close(self) -> None:
        async def run() -> tuple[list[str], int]:
            broker = EventBroker()
            gen = stream_events(broker, keepalive_seconds=5, now=system_now)
            frames = [await next_frame(gen)]
            broker.publish(ev(1))
            frames.append(await next_frame(gen))
            await gen.aclose()
            return frames, broker.subscriber_count

        frames, remaining = asyncio.run(run())
        assert frames[0] == ": connected\n\n"
        assert frames[1].startswith("event: order_created\ndata: ")
        assert remaining == 0

    def test_keepalive_comment_is_sent_periodically(self) -> None:
        async def run() -> list[str]:
            broker = EventBroker()
            gen = stream_events(broker, keepalive_seconds=0.05, now=system_now)
            frames = [await next_frame(gen) for _ in range(3)]
            await gen.aclose()
            return frames

        assert asyncio.run(run()) == [": connected\n\n", ": keep-alive\n\n", ": keep-alive\n\n"]

    def test_stream_ends_when_token_expires(self) -> None:
        async def run() -> tuple[list[str], int]:
            broker = EventBroker()
            expires_at = int(time.time()) + 1
            frames = []
            async for frame in stream_events(broker, keepalive_seconds=0.2, expires_at=expires_at, now=system_now):
                frames.append(frame)
                if len(frames) > 50:
                    break
            return frames, broker.subscriber_count

        frames, remaining = asyncio.run(run())
        assert len(frames) <= 50  # 스스로 끝났다
        assert remaining == 0

    def test_already_expired_token_yields_nothing_after_connected(self) -> None:
        async def run() -> list[str]:
            broker = EventBroker()
            return [f async for f in stream_events(broker, keepalive_seconds=1, expires_at=1, now=system_now)]

        assert asyncio.run(run()) == [": connected\n\n"]

    def test_stream_ends_on_overflow_and_on_shutdown(self) -> None:
        async def run(trigger: str) -> list[str]:
            broker = EventBroker(queue_size=1)
            gen = stream_events(broker, keepalive_seconds=5, now=system_now)
            frames = [await next_frame(gen)]
            if trigger == "overflow":
                broker.publish(ev(1))
                broker.publish(ev(2))
            else:
                broker.close_all()
            async for frame in gen:
                frames.append(frame)
            assert broker.subscriber_count == 0
            return frames

        assert asyncio.run(run("overflow")) == [": connected\n\n"]
        assert asyncio.run(run("shutdown")) == [": connected\n\n"]

    def test_cancellation_releases_subscription(self) -> None:
        async def run() -> int:
            broker = EventBroker()

            async def consume() -> None:
                async for _ in stream_events(broker, keepalive_seconds=5, now=system_now):
                    pass

            task = asyncio.create_task(consume())
            await asyncio.sleep(0.05)
            assert broker.subscriber_count == 1
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            return broker.subscriber_count

        assert asyncio.run(run()) == 0

    def test_expiry_uses_injected_clock(self) -> None:
        base = datetime(2026, 10, 14, tzinfo=timezone.utc)
        offset = {"seconds": 0}

        def now() -> datetime:
            return base + timedelta(seconds=offset["seconds"])

        async def run() -> list[str]:
            broker = EventBroker()
            expires_at = int(base.timestamp()) + 3600
            gen = stream_events(broker, keepalive_seconds=0.05, expires_at=expires_at, now=now)
            frames = [await next_frame(gen), await next_frame(gen)]
            offset["seconds"] = 3601  # 만료 시각을 지나도록 시계를 이동
            async for frame in gen:
                frames.append(frame)
            return frames

        frames = asyncio.run(run())
        assert frames[0] == ": connected\n\n"
        assert frames[1] == ": keep-alive\n\n"
