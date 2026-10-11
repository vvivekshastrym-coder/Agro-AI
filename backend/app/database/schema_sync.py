"""Additive schema sync.

`Base.metadata.create_all()` creates missing tables but never adds columns that were
introduced to an existing model later. That drift caused 500 errors in production
(e.g. `logistics_trips.trip_pin` missing). This helper adds any missing *nullable or
defaulted* columns via `ALTER TABLE ... ADD COLUMN`. It never drops, renames or
rewrites anything, so existing data is always preserved.
"""
import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def _default_sql(col):
    d = col.default
    if d is None or not getattr(d, "is_scalar", False):
        return None
    v = d.arg
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    if hasattr(v, "value"):  # Enum member
        return "'" + str(v.value).replace("'", "''") + "'"
    return None


def sync_missing_columns(engine: Engine, metadata) -> list:
    added = []
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in present:
                    continue
                default = _default_sql(col)
                if not col.nullable and default is None:
                    logger.warning("Schema sync: cannot auto-add NOT NULL column %s.%s without a default", table.name, col.name)
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(dialect=engine.dialect)}'
                if default is not None:
                    ddl += f" DEFAULT {default}"
                conn.execute(text(ddl))
                added.append(f"{table.name}.{col.name}")
    if added:
        logger.info("Schema sync added columns: %s", ", ".join(added))
    return added
