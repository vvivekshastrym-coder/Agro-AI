"""Authoritative FastAPI Application entrypoint for Vercel deployment."""
from backend.app.main import app

__all__ = ["app"]
