from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import time
import os
from .database.connection import engine, Base
from .routers import auth, agri, weather, market, satellite, diagnosis, agro_gpt, logistics, marketplace, drone, admin, plans, payments, schemes, mart
from .routers.logistics import trip_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── DB Table Creation ────────────────────────────────────────
Base.metadata.create_all(bind=engine)
try:
    from .database.schema_sync import sync_missing_columns
    sync_missing_columns(engine, Base.metadata)
except Exception as _e:  # never block startup on sync problems
    logger.error("Schema sync failed: %s", _e)

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
_allowed_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000,http://localhost:5173")
ALLOWED_ORIGINS = [orig.strip() for orig in _allowed_raw.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

from fastapi.responses import JSONResponse

_BLOCKED_PREFIXES = (
    "/backend", "/supabase", "/prisma", "/exports", "/scripts", "/releases",
    "/android", "/ios", "/flutter_app", "/node_modules", "/utils", "/docs/"
)
_BLOCKED_EXTENSIONS = (
    ".db", ".sqlite", ".sqlite3", ".sql", ".py", ".pyc", ".env",
    ".bak", ".jks", ".aab", ".apk", ".toml", ".lock", ".ts"
)
_BLOCKED_FILENAMES = {
    "package.json", "package-lock.json", "skills-lock.json",
    "dockerfile", "procfile", "vercel.json", "components.json"
}

@app.middleware('http')
async def add_security_headers(request: Request, call_next):
    raw_path = request.url.path or "/"
    norm_path = raw_path.lower()
    segments = [seg for seg in norm_path.split("/") if seg]
    # Block dot-files/directories (.env, .git, .claude, etc.) and internal server directories
    if (
        any(seg.startswith(".") for seg in segments)
        or any(norm_path == p or norm_path.startswith(p + "/") for p in _BLOCKED_PREFIXES)
        or (not norm_path.startswith("/api/") and norm_path.endswith(_BLOCKED_EXTENSIONS))
        or (segments and segments[-1] in _BLOCKED_FILENAMES)
    ):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(self), microphone=(self), geolocation=(self)'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    if raw_path in ('/', '/index.html', '/sw.js', '/privacy', '/delete-account') or raw_path.endswith(('.html', '.js')):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

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
app.include_router(admin.router,       prefix='/api/admin',       tags=['Admin Console'])
app.include_router(plans.router,       prefix='/api/plans',       tags=['Subscription Plans'])
app.include_router(payments.router,    prefix='/api/payments',    tags=['Payments'])
app.include_router(schemes.router,     prefix='/api/schemes',     tags=['Government Schemes'])
app.include_router(mart.router,        prefix='/api/mart',        tags=['Agro AI Mart'])
app.include_router(mart.admin_router,  prefix='/api/admin/mart',  tags=['Agro AI Mart Admin'])

@app.get('/docs', include_in_schema=False)
async def redirect_docs():
    return RedirectResponse('/api/docs')

# ─── Health & Honest Status ────────────────────────────────────
@app.get('/api/health', tags=['Health'])
async def health_check():
    from .database.connection import SessionLocal
    from sqlalchemy import text
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_ok = True
        db.close()
    except Exception:
        db_ok = False

    return {
        'status': 'healthy' if db_ok else 'degraded',
        'version': '2.0.0',
        'service': 'Agro AI Production Backend',
        'database_connected': db_ok,
        'demo_seed_mode': os.getenv('ALLOW_DEMO_SEED') == '1',
        'supabase_configured': bool(os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_PUBLISHABLE_KEY')),
        'razorpay_configured': bool(os.getenv('RAZORPAY_KEY_ID') and os.getenv('RAZORPAY_KEY_SECRET')),
        'openweather_configured': bool(os.getenv('OPENWEATHER_API_KEY')),
        'gemini_configured': bool(os.getenv('GEMINI_API_KEY'))
    }


# ─── Public Farmer Broadcasts & Promotional Offers ─────────────
@app.get('/api/broadcasts', tags=['Announcements & Offers'])
async def get_public_broadcasts():
    """Returns all Super Admin-approved announcements, advisory tips, and promotional offers live for farmers."""
    from .database.connection import SessionLocal
    from .database.models import BroadcastItem, BroadcastStatus
    import datetime
    db = SessionLocal()
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        items = db.query(BroadcastItem).filter(
            BroadcastItem.status == BroadcastStatus.approved
        ).order_by(BroadcastItem.created_at.desc()).all()

        out = []
        for it in items:
            # Check validity dates if set
            if it.valid_until and it.valid_until < now:
                continue
            out.append({
                "id": it.id,
                "item_type": it.item_type.value,
                "title": it.title,
                "content": it.content,
                "discount_percent": it.discount_percent,
                "discount_code": it.discount_code,
                "target_plan_slug": it.target_plan_slug,
                "banner_url": it.banner_url,
                "tags": it.tags or [],
                "valid_until": it.valid_until.isoformat() if it.valid_until else None,
                "created_at": it.created_at.isoformat() if it.created_at else None
            })
        return out
    finally:
        db.close()


@app.get('/api/offers', tags=['Announcements & Offers'])
async def get_public_offers():
    """Returns active promotional discount offers approved by Super Admin."""
    all_broadcasts = await get_public_broadcasts()
    return [b for b in all_broadcasts if b["item_type"] == "offer"]

# ─── WebSocket — Real-time Driver GPS ─────────────────────────
@app.websocket('/ws/trip/{trip_id}')
async def websocket_trip_tracking(websocket: WebSocket, trip_id: str, token: str = ''):
    """
    Real-time GPS tracking channel for a trip.
    - Customer connects here to receive live driver location updates.
    - Driver pushes GPS via POST /api/logistics/drivers/location which
      broadcasts to all connected customers for that trip_id.
    """
    from .database.connection import SessionLocal
    from .database.models import LogisticsTrip
    import hmac as _hmac
    _db = SessionLocal()
    try:
        _trip = _db.query(LogisticsTrip).filter(LogisticsTrip.id == trip_id).first()
        _ok = bool(_trip and token and _trip.share_token and _hmac.compare_digest(token, _trip.share_token))
    finally:
        _db.close()
    if not _ok:
        await websocket.close(code=4403)
        return
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

# ─── Mount Frontend Static Files & Admin Console SPA ─────────
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
admin_dist = os.path.join(project_root, "admin", "dist")

if os.path.exists(admin_dist):
    admin_assets = os.path.join(admin_dist, "assets")
    if os.path.exists(admin_assets):
        app.mount("/admin/assets", StaticFiles(directory=admin_assets), name="admin_assets")

    @app.get("/admin")
    @app.get("/admin/")
    @app.get("/admin/{full_path:path}")
    async def serve_admin_spa(full_path: str = ""):
        # Check if requesting a direct existing file in admin_dist
        if full_path:
            target_file = os.path.join(admin_dist, full_path)
            if os.path.isfile(target_file):
                return FileResponse(target_file)
        # Fallback to SPA index.html for client-side routing
        index_file = os.path.join(admin_dist, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Admin console build not found")

@app.get("/privacy", include_in_schema=False)
async def serve_privacy_policy():
    privacy_file = os.path.join(project_root, "privacy.html")
    if os.path.isfile(privacy_file):
        return FileResponse(privacy_file)
    raise HTTPException(status_code=404, detail="Privacy policy not found")


@app.get("/delete-account", include_in_schema=False)
async def serve_delete_account_page():
    delete_file = os.path.join(project_root, "delete-account.html")
    if os.path.isfile(delete_file):
        return FileResponse(delete_file)
    raise HTTPException(status_code=404, detail="Account deletion page not found")


if os.path.exists(project_root):
    app.mount("/", StaticFiles(directory=project_root, html=True), name="frontend")


