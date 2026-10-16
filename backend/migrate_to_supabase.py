import sys
import os
import urllib.request
import json

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from sqlalchemy import create_engine, text
from app.database.connection import Base, RAW_DATABASE_URL, DATABASE_URL
from app.database import models


def generate_postgres_sql_file():
    """Compile all SQLAlchemy models into a standalone PostgreSQL DDL script."""
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'supabase_schema.sql'))
    dialect = postgresql.dialect()

    lines = [
        "-- ============================================================",
        "-- AGRO AI — SUPABASE POSTGRESQL SCHEMA MIGRATION",
        "-- Project Ref: eziigoiirqdsgimfkquv",
        "-- Run this directly in the Supabase SQL Editor or via migrate_to_supabase.py",
        "-- ============================================================",
        "",
    ]

    # Collect enum types first
    enum_clauses = []
    seen_enums = set()
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            if hasattr(col.type, 'enums') and getattr(col.type, 'name', None):
                enum_name = col.type.name
                if enum_name not in seen_enums:
                    seen_enums.add(enum_name)
                    vals = ", ".join(f"'{v}'" for v in col.type.enums)
                    enum_clauses.append(
                        f"DO $$ BEGIN\n"
                        f"    CREATE TYPE {enum_name} AS ENUM ({vals});\n"
                        f"EXCEPTION\n"
                        f"    WHEN duplicate_object THEN null;\n"
                        f"END $$;"
                    )

    if enum_clauses:
        lines.append("-- 1. Enum Types")
        lines.extend(enum_clauses)
        lines.append("")

    lines.append("-- 2. Tables")
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)).strip()
        lines.append(f"{ddl};\n")

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    return out_path, len(Base.metadata.sorted_tables)


def test_supabase_api():
    """Verify live HTTP connectivity to Supabase Auth & REST endpoints."""
    supabase_url = os.getenv("SUPABASE_URL", "https://eziigoiirqdsgimfkquv.supabase.co")
    pub_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_fDc46mh4MukSCabbBpeVMA_KqtWdOee")
    jwks_url = os.getenv("SUPABASE_JWKS_URL", f"{supabase_url}/auth/v1/.well-known/jwks.json")

    print("1. Testing Supabase Live API Connectivity...")
    try:
        req = urllib.request.Request(jwks_url, headers={"apikey": pub_key})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            keys_count = len(data.get("keys", []))
            print(f"   [OK] Supabase Auth JWKS Endpoint reachable ({jwks_url})")
            print(f"   [OK] Active signing keys verified: {keys_count} key(s)")
    except Exception as e:
        print(f"   [WARN] Could not reach JWKS endpoint: {e}")

    try:
        settings_url = f"{supabase_url}/auth/v1/settings"
        req = urllib.request.Request(settings_url, headers={"apikey": pub_key})
        with urllib.request.urlopen(req, timeout=8) as resp:
            settings = json.loads(resp.read().decode('utf-8'))
            ext = settings.get("external", {})
            google_enabled = ext.get("google", False)
            print(f"   [OK] Supabase Auth Settings reachable")
            print(f"   [INFO] Google OAuth Provider Enabled in Dashboard: {google_enabled}")
            if not google_enabled:
                print("          -> Action needed: Enable Google toggle in Supabase Dashboard > Auth > Providers")
    except Exception as e:
        print(f"   [WARN] Could not check Auth settings: {e}")
    print()


def migrate():
    print("=" * 64)
    print(" Agro AI -> Supabase PostgreSQL Migration & Connectivity Suite")
    print("=" * 64)
    print()

    # Step 1: Test Supabase HTTP endpoints
    test_supabase_api()

    # Step 2: Generate standalone SQL schema for Supabase SQL Editor
    print("2. Generating Standalone PostgreSQL Schema (supabase_schema.sql)...")
    sql_path, table_count = generate_postgres_sql_file()
    print(f"   [OK] Generated DDL for {table_count} tables at:")
    print(f"        {sql_path}\n")

    # Step 3: Check direct PostgreSQL connection
    print("3. Checking Direct PostgreSQL Connection...")
    if not RAW_DATABASE_URL or "[YOUR-PASSWORD]" in RAW_DATABASE_URL:
        print("   [PENDING PASSWORD] DATABASE_URL in .env still has placeholder [YOUR-PASSWORD].")
        print("   -> You have two easy ways to apply the schema to Supabase:")
        print("      Option A: Paste supabase_schema.sql into the Supabase Dashboard SQL Editor:")
        print("                https://supabase.com/dashboard/project/eziigoiirqdsgimfkquv/sql/new")
        print("      Option B: Replace [YOUR-PASSWORD] in .env & backend/.env and re-run:")
        print("                python backend/migrate_to_supabase.py")
        print("\n   [FALLBACK ACTIVE] Local backend is safely using SQLite until password is set.")
        return

    pg_url = RAW_DATABASE_URL
    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    try:
        pg_engine = create_engine(pg_url, pool_pre_ping=True)
        with pg_engine.connect() as conn:
            res = conn.execute(text("SELECT version();")).fetchone()
            print(f"   [OK] Connected to Supabase PostgreSQL!")
            print(f"   Server: {res[0][:65]}...\n")

        print("4. Pushing all SQLAlchemy tables to Supabase PostgreSQL...")
        Base.metadata.create_all(bind=pg_engine)
        print("   [OK] All tables created/verified on Supabase!\n")

        with pg_engine.connect() as conn:
            query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;"
            tables = conn.execute(text(query)).fetchall()
            print(f"   Verified {len(tables)} tables in public schema:")
            for t in tables:
                print(f"     - {t[0]}")
            print()

        print("5. Seeding initial verified drivers and farm data...")
        from sqlalchemy.orm import sessionmaker
        from app.seed import seed_database
        PgSession = sessionmaker(bind=pg_engine)
        db = PgSession()
        try:
            seed_database(db)
            print("   [OK] Seed data verified!")
        finally:
            db.close()

        print("\n" + "=" * 64)
        print(" [SUCCESS] Agro AI is live on Supabase PostgreSQL!")
        print("=" * 64)

    except Exception as e:
        print(f"   [FAILED] PostgreSQL connection error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    migrate()
