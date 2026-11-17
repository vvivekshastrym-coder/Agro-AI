import os, sys, tempfile

_tmp = tempfile.mkdtemp()
test_db_path = os.path.join(_tmp, "test_suite.db").replace("\\", "/")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ["SUPABASE_JWKS_URL"] = "https://example.invalid/jwks"
os.environ.pop("SUPABASE_JWT_SECRET", None)
os.environ["ENVIRONMENT"] = "test"
os.environ["ALLOW_DEMO_SEED"] = "1"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Pre-initialize schema in isolated temporary test database so tests never touch production kisanai.db
from app.database.connection import engine, Base
import app.database.models  # ensure all models registered
Base.metadata.create_all(bind=engine)

# Existing tests simulate the mobile app (logistics APIs are app-only). Tests that
# check web behaviour pass an explicit "X-Agro-Client: web" header to override.
from fastapi.testclient import TestClient as _TC
_orig_init = _TC.__init__
def _init_with_app_header(self, *a, **kw):
    _orig_init(self, *a, **kw)
    self.headers.setdefault("X-Agro-Client", "app")
_TC.__init__ = _init_with_app_header
