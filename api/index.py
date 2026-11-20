"""Vercel Python Serverless Function entrypoint for Agro AI FastAPI backend."""
import pathlib
import sys
import traceback

ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from backend.app.main import app  # noqa: E402,F401

    @app.middleware("http")
    async def restore_original_vercel_path(request, call_next):
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
except Exception as _init_err:
    _err_msg = "".join(traceback.format_exception(_init_err))
    print(f"CRITICAL: Failed to import backend.app.main: {_err_msg}", file=sys.stderr)
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def import_error_fallback(path: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "BACKEND_STARTUP_FAILED",
                    "message": str(_init_err),
                    "traceback": _err_msg.splitlines()[-6:],
                }
            }
        )
