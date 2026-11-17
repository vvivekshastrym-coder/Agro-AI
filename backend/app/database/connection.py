from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load .env from backend/.env or root .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))

RAW_DATABASE_URL = os.getenv('DATABASE_URL', '')
root_db = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'kisanai.db'))
SQLITE_FALLBACK_URL = f"sqlite:///{root_db.replace(os.sep, '/')}"

if not RAW_DATABASE_URL or '[YOUR-PASSWORD]' in RAW_DATABASE_URL:
    DATABASE_URL = SQLITE_FALLBACK_URL
else:
    DATABASE_URL = RAW_DATABASE_URL

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

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
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        pool_timeout=30
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
