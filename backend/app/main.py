from datetime import datetime, timezone

import sentry_sdk
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler
from sqlalchemy import text

from .config import get_settings
from .db import AsyncSessionLocal
from .rate_limit import limiter
from .routers import auth, public, wishlists
from .services.realtime import hub

settings = get_settings()
app = FastAPI(title=settings.app_name)

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[FastApiIntegration()],
    )

origins = [origin.strip() for origin in settings.cors_origins.split(',') if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.get('/health')
async def health() -> dict[str, str | bool]:
    db_ok = True
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text('SELECT 1'))
    except Exception:
        db_ok = False
    return {
        'status': 'ok' if db_ok else 'degraded',
        'db': db_ok,
        'environment': settings.environment,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


@app.websocket('/ws/w/{share_token}')
async def wishlist_ws(websocket: WebSocket, share_token: str) -> None:
    await hub.connect(share_token, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(share_token, websocket)
    except Exception:
        hub.disconnect(share_token, websocket)


app.include_router(auth.router)
app.include_router(wishlists.router)
app.include_router(public.router)
