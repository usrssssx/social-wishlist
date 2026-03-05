from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

import sentry_sdk
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sentry_sdk.integrations.fastapi import FastApiIntegration
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from .config import get_settings
from .db import AsyncSessionLocal
from .errors import register_error_handlers
from .rate_limit import limiter
from .routers import auth, public, webhooks, wishlists
from .services.monitoring_service import monitor
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
register_error_handlers(app)
app.add_middleware(SlowAPIMiddleware)


@app.get('/health')
async def health() -> dict[str, str | bool]:
    metrics = monitor.snapshot()
    db_ok = True
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text('SELECT 1'))
    except Exception:
        db_ok = False
    overloaded = metrics.errors_5xx_last_5m >= settings.health_5xx_threshold_5m
    status_value = 'ok'
    if not db_ok or overloaded:
        status_value = 'degraded'
    return {
        'status': status_value,
        'db': db_ok,
        'errors_5xx_last_5m': metrics.errors_5xx_last_5m,
        'requests_last_5m': metrics.requests_last_5m,
        'environment': settings.environment,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


@app.get('/health/metrics')
async def health_metrics() -> dict[str, int]:
    metrics = monitor.snapshot()
    return {
        'requests_last_5m': metrics.requests_last_5m,
        'errors_4xx_last_5m': metrics.errors_4xx_last_5m,
        'errors_5xx_last_5m': metrics.errors_5xx_last_5m,
    }


@app.middleware('http')
async def monitoring_middleware(request: Request, call_next) -> Response:
    request_id = request.headers.get('x-request-id') or uuid4().hex
    started = perf_counter()
    response: Response | None = None
    try:
        response = await call_next(request)
        return response
    except Exception:
        monitor.record(500)
        raise
    finally:
        if response is not None:
            monitor.record(response.status_code)
            response.headers['X-Request-Id'] = request_id
            response.headers['X-Response-Time-Ms'] = str(round((perf_counter() - started) * 1000, 2))


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
app.include_router(webhooks.router)
