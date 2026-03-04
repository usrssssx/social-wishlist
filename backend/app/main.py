from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import Base, engine
from .routers import auth, public, wishlists
from .services.realtime import hub

settings = get_settings()
app = FastAPI(title=settings.app_name)

origins = [origin.strip() for origin in settings.cors_origins.split(',') if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.on_event('startup')
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok'}


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
