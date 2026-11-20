"""Vercel Python Serverless Function entrypoint for Agro AI FastAPI backend."""
import pathlib
import sys
from urllib.parse import parse_qs, parse_qsl, urlencode

# Ensure repository root is on Python module search path
ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.app.main import app as _app


class VercelPathRewriter:
    """ASGI Middleware that restores original requested API paths before FastAPI routing."""

    def __init__(self, app):
        self.app = app

    def __getattr__(self, name):
        return getattr(self.app, name)

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            if path in ("/api/index.py", "/api/index", "/api", "/index.py", "/index", ""):
                qs = scope.get("query_string", b"").decode("latin-1")
                params = parse_qs(qs)
                if "path" in params and params["path"]:
                    target = params["path"][0].lstrip("/")
                    if not target.startswith("api/"):
                        target = f"api/{target}"
                    scope["path"] = f"/{target}".split("?")[0]
                    scope["raw_path"] = scope["path"].encode("utf-8")
                    filtered = [(k, v) for k, v in parse_qsl(qs) if k != "path"]
                    scope["query_string"] = urlencode(filtered).encode("latin-1")
                else:
                    for header_name, header_val in scope.get("headers", []):
                        h_name = header_name.decode("latin-1").lower()
                        if h_name in ("x-forwarded-uri", "x-original-url", "x-real-path"):
                            h_val = header_val.decode("latin-1").split("?")[0]
                            if h_val not in ("/api/index.py", "/api/index", "/api", "/index.py", "/index", ""):
                                scope["path"] = h_val
                                scope["raw_path"] = h_val.encode("utf-8")
                                break
        await self.app(scope, receive, send)


# Top-level ASGI application instance for Vercel deployment detection
app = VercelPathRewriter(_app)
