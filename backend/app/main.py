from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import time
import os
from .database.connection import engine, Base
from .routers import auth, agri, weather, market, satellite, diagnosis, agro_gpt, logistics, marketplace, drone
from .routers.logistics import trip_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── DB Table Creation ────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ─── Rate Limiter ─────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ─── App ──────────────────────────────────────────────────────
app = FastAPI(
    title='Agro AI Unified Backend API',
    description='Single Source of Truth for Leaf Diagnosis, Agro GPT, Logistics, and Inputs',
    version='2.0.0',
    docs_url='/api/docs',
    redoc_url='/api/redoc'
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── Middleware ───────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.middleware('http')
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    response.headers['X-Process-Time'] = f'{process_time:.2f}ms'
    return response

@app.middleware('http')
async def log_requests(request: Request, call_next):
    logger.info(f'→ {request.method} {request.url.path}')
    response = await call_next(request)
    logger.info(f'← {response.status_code} {request.url.path}')
    return response

# ─── Routers ──────────────────────────────────────────────────
app.include_router(auth.router,        prefix='/api/auth',        tags=['Authentication'])
app.include_router(diagnosis.router,   prefix='/api/diagnosis',   tags=['Leaf Diagnosis'])
app.include_router(agro_gpt.router,    prefix='/api/agro-gpt',    tags=['Agro GPT'])
app.include_router(logistics.router,   prefix='/api/logistics',   tags=['Logistics'])
app.include_router(marketplace.router, prefix='/api/market',      tags=['Input Marketplace'])
app.include_router(drone.router,       prefix='/api/drone',       tags=['Drone Scout'])
app.include_router(market.router,      prefix='/api/market',      tags=['Mandi Prices'])
app.include_router(weather.router,     prefix='/api/weather',     tags=['Weather'])
app.include_router(agri.router,        prefix='/api/agri',        tags=['Agriculture'])
app.include_router(satellite.router,   prefix='/api/satellite',   tags=['Satellite'])

# ─── Health & Info ────────────────────────────────────────────
@app.get('/api/health', tags=['Health'])
async def health_check():
    return {
        'status': 'healthy',
        'version': '2.0.0',
        'service': 'Agro AI Single Source of Truth Backend'
    }

# ─── WebSocket — Real-time Driver GPS ─────────────────────────
@app.websocket('/ws/trip/{trip_id}')
async def websocket_trip_tracking(websocket: WebSocket, trip_id: str):
    """
    Real-time GPS tracking channel for a trip.
    - Customer connects here to receive live driver location updates.
    - Driver pushes GPS via POST /api/logistics/drivers/location which
      broadcasts to all connected customers for that trip_id.
    """
    await trip_manager.connect(trip_id, websocket)
    logger.info(f'[WS] Client connected to trip {trip_id}')
    try:
        while True:
            # Keep connection alive; actual messages are pushed via trip_manager.broadcast
            data = await websocket.receive_text()
            if data == 'ping':
                await websocket.send_text('pong')
    except WebSocketDisconnect:
        trip_manager.disconnect(trip_id, websocket)
        logger.info(f'[WS] Client disconnected from trip {trip_id}')

# ─── Mount Frontend Static Files ──────────────────────────────
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.exists(project_root):
    app.mount("/", StaticFiles(directory=project_root, html=True), name="frontend")
