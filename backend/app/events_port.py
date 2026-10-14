"""서버 이벤트 포트. backend-core는 발행 인터페이스만 알고, 실제 EventBroker는 backend-order가 제공한다."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger("app.events")


@dataclass(frozen=True)
class ServerEvent:
    # order_created | order_status_changed | order_deleted | session_ended | menu_changed
    type: str
    table_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class EventPublisher(Protocol):
    def publish(self, event: ServerEvent) -> None: ...


class NullPublisher:
    """기본 발행기: 아무 동작도 하지 않는다."""

    def publish(self, event: ServerEvent) -> None:  # noqa: D401
        return None


def safe_publish(publisher: EventPublisher, event: ServerEvent) -> None:
    """발행 실패가 이미 커밋된 요청을 실패시키지 않도록 예외를 삼키고 기록한다."""
    try:
        publisher.publish(event)
    except Exception:  # noqa: BLE001
        logger.exception("이벤트 발행에 실패했어요: %s", event.type)
