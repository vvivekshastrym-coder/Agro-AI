from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load .env from backend/.env or root .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))

_env = (os.getenv("VERCEL_ENV") or os.getenv("ENVIRONMENT") or "development").strip().lower()
_is_prod = _env in ("production", "prod")

RAW_DATABASE_URL = (
    os.getenv('DATABASE_URL')
    or os.getenv('POSTGRES_URL')
    or os.getenv('POSTGRES_URL_NON_POOLING')
    or ''
)
root_db = '/tmp/kisanai.db' if os.getenv('VERCEL') else os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'kisanai.db'))
SQLITE_FALLBACK_URL = f"sqlite:///{root_db.replace(os.sep, '/')}"

if not RAW_DATABASE_URL or '[YOUR-PASSWORD]' in RAW_DATABASE_URL:
    if _is_prod:
        import logging as _logging
        _logging.getLogger(__name__).critical("Production DATABASE_URL not configured! Ephemeral SQLite fallback in production is strictly prohibited.")
    DATABASE_URL = SQLITE_FALLBACK_URL
else:
    DATABASE_URL = RAW_DATABASE_URL

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

_engine_connect_args = {}
if DATABASE_URL.startswith('postgresql://'):
    try:
        import psycopg2  # noqa: F401
        _engine_connect_args = {'connect_timeout': 5}
    except ImportError:
        try:
            import psycopg  # noqa: F401
            from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
            DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
            parts = urlsplit(DATABASE_URL)
            qs = [(k, v) for k, v in parse_qsl(parts.query) if k != 'supa']
            DATABASE_URL = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(qs), ''))
            _engine_connect_args = {'connect_timeout': 5, 'prepare_threshold': None}
        except ImportError:
            import ssl
            from urllib.parse import urlsplit, urlunsplit
            DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+pg8000://', 1)
            parts = urlsplit(DATABASE_URL)
            DATABASE_URL = urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
            _ssl_ctx = ssl.create_default_context()
            if _is_prod and os.getenv("POSTGRES_INSECURE_TLS", "0") != "1":
                _ssl_ctx.check_hostname = True
                _ssl_ctx.verify_mode = ssl.CERT_REQUIRED
            else:
                _ssl_ctx.check_hostname = False
                _ssl_ctx.verify_mode = ssl.CERT_NONE
            _engine_connect_args = {'ssl_context': _ssl_ctx, 'timeout': 5}

if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(
        DATABASE_URL,
        connect_args={'check_same_thread': False, 'timeout': 15}
    )
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
        except Exception:
            pass
else:
    if os.getenv('VERCEL'):
        from sqlalchemy.pool import NullPool
        _pg_engine = create_engine(
            DATABASE_URL,
            connect_args={**_engine_connect_args, 'connect_timeout': 1},
            poolclass=NullPool,
        )
        try:
            from sqlalchemy import text as _sa_text
            with _pg_engine.connect() as _conn:
                _conn.execute(_sa_text("SELECT 1"))
            engine = _pg_engine
        except Exception as _pg_err:
            import logging as _logging
            allow_fallback = os.getenv("ALLOW_EPHEMERAL_DB_FALLBACK", "1").strip().lower() in ("1", "true", "yes")
            if allow_fallback or not _is_prod:
                _logging.getLogger(__name__).warning("Vercel Postgres unreachable (%s); using resilient /tmp/kisanai.db so services remain available while Supabase is paused. Set ALLOW_EPHEMERAL_DB_FALLBACK=0 to enforce strict database rejection.", type(_pg_err).__name__)
                DATABASE_URL = "sqlite:////tmp/kisanai.db"
                engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False, 'timeout': 15})
            else:
                _logging.getLogger(__name__).critical("Vercel Postgres unreachable (%s) in PRODUCTION. Ephemeral fallback disabled by ALLOW_EPHEMERAL_DB_FALLBACK=0.", type(_pg_err).__name__)
                engine = _pg_engine
    else:
        engine = create_engine(
            DATABASE_URL,
            connect_args=_engine_connect_args,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
            pool_timeout=8
        )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
