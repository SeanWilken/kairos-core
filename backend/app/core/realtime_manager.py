from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class RealtimeManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()

    def disconnect(self, websocket: WebSocket) -> None:
        for sockets in self._rooms.values():
            sockets.discard(websocket)

    def subscribe(self, *, room: str, websocket: WebSocket) -> None:
        self._rooms[room].add(websocket)

    def unsubscribe(self, *, room: str, websocket: WebSocket) -> None:
        self._rooms[room].discard(websocket)

    async def publish(self, *, room: str, event: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for socket in list(self._rooms.get(room, set())):
            try:
                await socket.send_json(event)
            except Exception:
                dead.append(socket)
        for socket in dead:
            self.disconnect(socket)


realtime_manager = RealtimeManager()
