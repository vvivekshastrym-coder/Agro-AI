"""Vercel Python Serverless Function entrypoint for Agro AI FastAPI backend."""
import pathlib
import sys

ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.app.main import app  # noqa: E402,F401
