import sys
import os

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database.connection import engine, Base, DATABASE_URL
from app.database import models
from sqlalchemy import text

def migrate():
    print(f'=' * 60)
    print(' Agro AI -> Supabase PostgreSQL Schema Migration & Test')
    print(f'=' * 60)
    
    # Hide password in logs
    safe_url = DATABASE_URL
    if '@' in safe_url:
        prefix, host_part = safe_url.split('@', 1)
        if ':' in prefix:
            proto_user = prefix.rsplit(':', 1)[0]
            safe_url = f'{proto_user}:****@{host_part}'
    print(f'Target Database: {safe_url}\n')

    if '[YOUR-PASSWORD]' in DATABASE_URL:
        print('[ERROR] Password placeholder [YOUR-PASSWORD] detected.')
        print('Please update DATABASE_URL in .env or backend/.env with your real Supabase DB password.')
        sys.exit(1)

    print('1. Testing database connectivity...')
    try:
        with engine.connect() as conn:
            res = conn.execute(text('SELECT version();')).fetchone()
            print(f'   [OK] Connected successfully!')
            print(f'   Engine version: {res[0][:60]}...\n')
    except Exception as e:
        print(f'   [FAILED] Could not connect to database.')
        print(f'   Error: {e}\n')
        sys.exit(1)

    print('2. Creating all schema tables on Supabase...')
    try:
        Base.metadata.create_all(bind=engine)
        print('   [OK] Tables created or verified!\n')
    except Exception as e:
        print(f'   [FAILED] Error creating tables: {e}\n')
        sys.exit(1)

    print('3. Verifying created tables...')
    try:
        with engine.connect() as conn:
            query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;"
            tables = conn.execute(text(query)).fetchall()
            print(f'   Found {len(tables)} tables in public schema:')
            for t in tables:
                print(f'     - {t[0]}')
            print()
    except Exception as e:
        print(f'   Verification error: {e}')

    print('4. Running initial driver & system seed...')
    try:
        from app.seed import seed_database
        from app.database.connection import SessionLocal
        db = SessionLocal()
        try:
            seed_database(db)
            print('   [OK] Verified drivers and sample farm data seeded!')
        finally:
            db.close()
    except Exception as e:
        print(f'   Notice on seeding: {e}')

    print('\n============================================================')
    print(' [SUCCESS] Agro AI is fully connected to Supabase PostgreSQL!')
    print('============================================================')

if __name__ == '__main__':
    migrate()
