"""Apply the additive Drone Services schema against the configured database."""
from pathlib import Path
import re

from sqlalchemy import Engine, text


MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "drone_services.sql"
MIGRATION_NAME = "drone_services_v1"


def _statements(source: str) -> list[str]:
    without_comments = re.sub(r"(?m)^\s*--.*$", "", source)
    return [part.strip() for part in without_comments.split(";") if part.strip()]


def apply_drone_migration(engine: Engine) -> bool:
    """Apply once under a Postgres advisory lock; return whether work was done."""
    if engine.dialect.name != "postgresql":
        return False
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "agro-ai-drone-services-v1"})
        conn.execute(text("CREATE TABLE IF NOT EXISTS drone_schema_migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"))
        applied = conn.execute(
            text("SELECT 1 FROM drone_schema_migrations WHERE name = :name"),
            {"name": MIGRATION_NAME},
        ).first()
        if applied:
            return False

        for statement in _statements(MIGRATION.read_text(encoding="utf-8")):
            conn.exec_driver_sql(statement)

        roles = {
            row[0]
            for row in conn.execute(text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')"))
        }
        tables = [
            "drone_companies", "drone_pilots", "drone_fleet", "drone_service_areas",
            "drone_applications", "drone_pilot_documents", "drone_approval_history",
            "drone_bookings", "drone_booking_status_history", "drone_role_assignments", "drone_reviews",
        ]
        for role in roles:
            conn.exec_driver_sql(f"REVOKE ALL PRIVILEGES ON TABLE {', '.join(tables)} FROM {role}")
        conn.exec_driver_sql("ALTER TABLE drone_schema_migrations ENABLE ROW LEVEL SECURITY")
        for role in roles:
            conn.exec_driver_sql(f"REVOKE ALL PRIVILEGES ON TABLE drone_schema_migrations FROM {role}")
        conn.execute(text("INSERT INTO drone_schema_migrations (name) VALUES (:name)"), {"name": MIGRATION_NAME})
    return True
