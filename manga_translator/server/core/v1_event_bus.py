"""Simple in-memory event bus for /api/v1/translate SSE."""

from __future__ import annotations

import asyncio
import json
from typing import Any


class V1EventBus:
    def __init__(self) -> None:
        self._listeners: set[asyncio.Queue[str]] = set()

    def add_listener(self, queue: asyncio.Queue[str]) -> None:
        self._listeners.add(queue)

    def remove_listener(self, queue: asyncio.Queue[str]) -> None:
        self._listeners.discard(queue)

    async def publish(self, payload: dict[str, Any]) -> None:
        if not self._listeners:
            return
        message = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        for queue in list(self._listeners):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    pass
            except Exception:
                self._listeners.discard(queue)


v1_event_bus = V1EventBus()
