"""Vercel Python Serverless Function entrypoint for Agro AI FastAPI backend."""
import pathlib
import sys
from urllib.parse import parse_qsl, urlencode

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
    raw_path = request.url.path or "/"

    # 1. If path is a generic entrypoint wrapper or root, restore from query param or header
    if raw_path.rstrip("/") in ("/api/index.py", "/api/index", "/api", "/index.py", "/index", ""):
        path_param = request.query_params.get("path")
        if path_param:
            clean = path_param.lstrip("/")
            if clean.startswith("api/"):
                request.scope["path"] = f"/{clean}".split("?")[0]
            else:
                request.scope["path"] = f"/api/{clean}".split("?")[0]
        else:
            for h in ("x-forwarded-uri", "x-original-url", "x-matched-path", "x-vercel-matched-path", "x-real-path"):
                orig = request.headers.get(h)
                if orig and orig.rstrip("/") not in ("/api/index.py", "/api/index", "/api", "/index.py", "/index", ""):
                    request.scope["path"] = orig.split("?")[0]
                    break

        # Remove internal routing query parameter if present
        if "path" in request.query_params:
            raw_qs = request.scope.get("query_string", b"").decode("latin-1")
            filtered_qs = [(k, v) for k, v in parse_qsl(raw_qs) if k != "path"]
            request.scope["query_string"] = urlencode(filtered_qs).encode("latin-1")

    # Sync raw_path bytes with restored scope path
    if "path" in request.scope:
        request.scope["raw_path"] = request.scope["path"].encode("utf-8")

    return await call_next(request)
