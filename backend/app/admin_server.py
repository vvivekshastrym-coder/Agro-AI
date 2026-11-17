import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Create a small FastAPI app that only serves the Admin console SPA
app = FastAPI(title="Agro AI Admin Server", docs_url=None, redoc_url=None)

# Resolve project root and admin build directory (same as main app)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
admin_dist = os.path.join(project_root, "admin", "dist")

# Mount any static assets under /admin/assets if they exist
admin_assets = os.path.join(admin_dist, "assets")
if os.path.isdir(admin_assets):
    app.mount("/admin/assets", StaticFiles(directory=admin_assets), name="admin_assets")

# Serve the Admin SPA – works for /admin, /admin/ and any client‑side route
@app.get("/admin")
@app.get("/admin/")
@app.get("/admin/{full_path:path}")
async def serve_admin(full_path: str = ""):
    # If a concrete file is requested, serve it directly
    if full_path:
        target_file = os.path.join(admin_dist, full_path)
        if os.path.isfile(target_file):
            return FileResponse(target_file)
    # Otherwise fall back to the SPA entry point
    index_file = os.path.join(admin_dist, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Admin console build not found")

# Optional health endpoint for the admin server
@app.get("/health")
async def health():
    return {"status": "ok", "service": "admin"}
