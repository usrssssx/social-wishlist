from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class RealtimeHub:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, share_token: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[share_token].add(websocket)

    def disconnect(self, share_token: str, websocket: WebSocket) -> None:
        if share_token not in self.connections:
            return
        self.connections[share_token].discard(websocket)
        if not self.connections[share_token]:
            self.connections.pop(share_token, None)

    async def broadcast(self, share_token: str, payload: dict[str, Any]) -> None:
        for ws in list(self.connections.get(share_token, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(share_token, ws)

    async def publish_update(self, share_token: str, event_type: str, item_id: str | None = None) -> None:
        await self.broadcast(
            share_token,
            {
                'type': event_type,
                'item_id': item_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            },
        )


hub = RealtimeHub()
