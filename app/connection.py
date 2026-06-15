from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from app.models import ConnectionRecord


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.records: dict[str, ConnectionRecord] = {}

    async def connect(self, websocket: WebSocket, record: ConnectionRecord) -> None:
        await websocket.accept()
        self.active_connections[record.connection_id] = websocket
        self.records[record.connection_id] = record

    def disconnect(self, connection_id: str) -> None:
        self.active_connections.pop(connection_id, None)
        self.records.pop(connection_id, None)

    async def send(self, connection_id: str, payload: dict[str, Any]) -> None:
        websocket = self.active_connections.get(connection_id)
        if websocket is None:
            return
        try:
            await websocket.send_json(payload)
        except RuntimeError:
            self.disconnect(connection_id)

    async def broadcast(
        self,
        payload: dict[str, Any],
        exclude_connection_id: str | None = None,
    ) -> None:
        for connection_id in list(self.active_connections):
            if connection_id == exclude_connection_id:
                continue
            await self.send(connection_id, payload)
