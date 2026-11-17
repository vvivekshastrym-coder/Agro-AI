"""Explicit gate for synthetic fixture data used only in isolated environments."""
import os


def demo_data_enabled() -> bool:
    environment = (
        os.getenv("ENVIRONMENT")
        or os.getenv("APP_ENV")
        or os.getenv("NODE_ENV")
        or ""
    ).strip().lower()
    return environment in {"development", "dev", "test", "testing"} and os.getenv("ALLOW_DEMO_SEED") == "1"
