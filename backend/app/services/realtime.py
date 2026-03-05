import asyncio
import inspect
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import WebSocket


class RealtimeHub:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)
        self.redis_url: str | None = None
        self.redis_channel: str = 'swl:realtime:events'
        self.instance_id = uuid4().hex
        self._redis_pub: Any | None = None
        self._redis_sub_client: Any | None = None
        self._redis_subscriber: Any | None = None
        self._redis_listener_task: asyncio.Task[None] | None = None
        self._logger = logging.getLogger(__name__)

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

    async def startup(self, redis_url: str | None, redis_channel: str) -> None:
        self.redis_url = (redis_url or '').strip() or None
        self.redis_channel = redis_channel
        if not self.redis_url:
            self._logger.info('Realtime hub started in local-only mode')
            return

        try:
            import redis.asyncio as redis  # type: ignore[import-not-found]
        except Exception:
            self._logger.exception('redis package is not installed, falling back to local-only realtime')
            return

        try:
            self._redis_pub = redis.from_url(self.redis_url, decode_responses=True)
            self._redis_sub_client = redis.from_url(self.redis_url, decode_responses=True)
            self._redis_subscriber = self._redis_sub_client.pubsub(ignore_subscribe_messages=True)
            await self._redis_subscriber.subscribe(self.redis_channel)
            self._redis_listener_task = asyncio.create_task(self._listen_redis(), name='realtime-redis-listener')
            self._logger.info('Realtime hub connected to Redis channel %s', self.redis_channel)
        except Exception:
            self._logger.exception('Failed to initialize Redis pub/sub, falling back to local-only realtime')
            await self._close_redis()

    async def shutdown(self) -> None:
        if self._redis_listener_task:
            self._redis_listener_task.cancel()
            try:
                await self._redis_listener_task
            except asyncio.CancelledError:
                pass
            except Exception:
                self._logger.exception('Realtime Redis listener stopped with error')
            finally:
                self._redis_listener_task = None
        await self._close_redis()

    async def _close_redis(self) -> None:
        async def _close_resource(resource: Any) -> None:
            close_fn = getattr(resource, 'aclose', None) or getattr(resource, 'close', None)
            if close_fn is None:
                return
            result = close_fn()
            if inspect.isawaitable(result):
                await result

        if self._redis_subscriber is not None:
            try:
                await self._redis_subscriber.unsubscribe(self.redis_channel)
                await _close_resource(self._redis_subscriber)
            except Exception:
                self._logger.exception('Failed to close Redis subscriber')
            finally:
                self._redis_subscriber = None

        for attr_name in ('_redis_pub', '_redis_sub_client'):
            client = getattr(self, attr_name, None)
            if client is None:
                continue
            try:
                await _close_resource(client)
            except Exception:
                self._logger.exception('Failed to close Redis client')
            finally:
                setattr(self, attr_name, None)

    async def _listen_redis(self) -> None:
        if self._redis_subscriber is None:
            return
        while True:
            message = await self._redis_subscriber.get_message(timeout=1.0)
            if not message:
                await asyncio.sleep(0.05)
                continue

            raw_data = message.get('data')
            if not raw_data:
                continue
            try:
                data = json.loads(raw_data)
            except Exception:
                continue

            if data.get('instance_id') == self.instance_id:
                continue
            share_token = str(data.get('share_token') or '').strip()
            payload = data.get('payload')
            if not share_token or not isinstance(payload, dict):
                continue
            await self.broadcast(share_token, payload)

    async def publish_update(self, share_token: str, event_type: str, item_id: str | None = None) -> None:
        payload = {
            'type': event_type,
            'item_id': item_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        await self.broadcast(share_token, payload)

        if self._redis_pub is None:
            return
        envelope = {
            'instance_id': self.instance_id,
            'share_token': share_token,
            'payload': payload,
        }
        try:
            await self._redis_pub.publish(self.redis_channel, json.dumps(envelope, ensure_ascii=True))
        except Exception:
            self._logger.exception('Failed to publish realtime event to Redis')


hub = RealtimeHub()
