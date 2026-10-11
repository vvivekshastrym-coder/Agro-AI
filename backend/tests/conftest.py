import os, sys, tempfile

_tmp = tempfile.mkdtemp()
test_db_path = os.path.join(_tmp, "test_suite.db").replace("\\", "/")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ["SUPABASE_JWKS_URL"] = "https://example.invalid/jwks"
os.environ.pop("SUPABASE_JWT_SECRET", None)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Pre-initialize schema in isolated temporary test database so tests never touch production kisanai.db
from app.database.connection import engine, Base
import app.database.models  # ensure all models registered
Base.metadata.create_all(bind=engine)
