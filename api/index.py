"""Vercel Python Serverless Function entrypoint for Agro AI FastAPI backend."""
import pathlib
import sys

# Ensure repository root is on Python module search path
ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Explicit top-level FastAPI application instance for Vercel AST builder detection
from backend.app.main import app as _app

app = _app


@app.middleware("http")
async def restore_original_vercel_path(request, call_next):
    """Normalize Vercel rewrite paths so FastAPI router matches original URLs."""
    raw_path = request.url.path
    if raw_path.rstrip("/") in ("/api/index.py", "/api/index", "/api", "/index.py", "/index", ""):
        restored = False
        for h in ("x-forwarded-uri", "x-original-url", "x-matched-path", "x-vercel-matched-path", "x-real-path"):
            orig = request.headers.get(h)
            if orig and orig.rstrip("/") not in ("/api/index.py", "/api/index", "/api", "/index.py", "/index", ""):
                request.scope["path"] = orig.split("?")[0]
                restored = True
                break
        if not restored:
            path_param = request.query_params.get("path")
            if path_param:
                clean = path_param.lstrip("/")
                if clean.startswith("api/"):
                    request.scope["path"] = f"/{clean}".split("?")[0]
                else:
                    request.scope["path"] = f"/api/{clean}".split("?")[0]
    return await call_next(request)
