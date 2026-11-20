"""Business logic service for querying, ingesting, and maintaining Mandi Market prices."""
from datetime import datetime, date
import logging
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from ...database.models import MandiPriceRecord, MandiMarket
from .market_validator import MandiPriceSchema, detect_and_resolve_conflicts, validate_raw_market_entry
from .market_sources import (
    AgmarknetSource,
    EnamSource,
    KarnatakaApmcSource,
    get_verified_reference_records,
)

logger = logging.getLogger(__name__)

_LAST_SUCCESSFUL_REFRESH: Optional[datetime] = None
_REFRESH_AUDIT_LOGS: List[Dict[str, Any]] = []


class MandiMarketService:
    """Core service for real-time Mandi market operations."""

    @classmethod
    def ensure_seed_data(cls, db: Session) -> int:
        """Seeds verified benchmark prices for initial Karnataka APMC markets if empty."""
        try:
            count = db.query(MandiPriceRecord).count()
        except Exception:
            db.rollback()
            try:
                from ...database.connection import Base, engine
                Base.metadata.create_all(bind=engine)
                count = db.query(MandiPriceRecord).count()
            except Exception as _e:
                logger.error("Failed to ensure mandi_prices table or seed data: %s", _e)
                return 0

        if count == 0:
            logger.info("Initializing mandi_prices table with verified initial APMC market benchmarks...")
            records = get_verified_reference_records()
            return cls.save_records(db, records)
        return 0

    @classmethod
    def save_records(cls, db: Session, records: List[MandiPriceSchema]) -> int:
        """Saves or updates validated Mandi price records in the database with conflict handling."""
        resolved = detect_and_resolve_conflicts(records)
        saved_count = 0

        for r in resolved:
            # Query existing entry by unique constraint
            existing = (
                db.query(MandiPriceRecord)
                .filter(
                    MandiPriceRecord.commodity == r.commodity,
                    MandiPriceRecord.market == r.market,
                    MandiPriceRecord.market_date == r.market_date,
                    MandiPriceRecord.unit == r.unit,
                    MandiPriceRecord.source_name == r.source_name,
                )
                .first()
            )

            if existing:
                existing.min_price = r.min_price
                existing.max_price = r.max_price
                existing.modal_price = r.modal_price
                existing.arrival_quantity = r.arrival_quantity
                existing.arrival_unit = r.arrival_unit
                existing.source_url = r.source_url
                existing.verification_status = r.verification_status
                existing.fetched_at = datetime.now()
                existing.updated_at = datetime.now()
            else:
                db_record = MandiPriceRecord(
                    commodity=r.commodity,
                    market=r.market,
                    district=r.district,
                    state=r.state,
                    min_price=r.min_price,
                    max_price=r.max_price,
                    modal_price=r.modal_price,
                    currency=r.currency,
                    unit=r.unit,
                    arrival_quantity=r.arrival_quantity,
                    arrival_unit=r.arrival_unit,
                    market_date=r.market_date,
                    source_name=r.source_name,
                    source_url=r.source_url,
                    fetched_at=datetime.now(),
                    verification_status=r.verification_status,
                )
                db.add(db_record)
            saved_count += 1

        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Error committing mandi price records: %s", exc)
            raise

        return saved_count

    @classmethod
    def get_prices(
        cls,
        db: Session,
        commodity: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        market: Optional[str] = None,
        market_date: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 20,
        page: int = 1,
    ) -> Dict[str, Any]:
        """Retrieves verified commodity prices with filtering, pagination, and metadata."""
        cls.ensure_seed_data(db)

        query = db.query(MandiPriceRecord)

        if commodity:
            query = query.filter(MandiPriceRecord.commodity.ilike(f"%{commodity.strip()}%"))
        if state:
            query = query.filter(MandiPriceRecord.state.ilike(f"%{state.strip()}%"))
        if district:
            query = query.filter(MandiPriceRecord.district.ilike(f"%{district.strip()}%"))
        if market:
            query = query.filter(MandiPriceRecord.market.ilike(f"%{market.strip()}%"))
        if market_date:
            query = query.filter(MandiPriceRecord.market_date == market_date.strip())
        if min_price is not None:
            query = query.filter(MandiPriceRecord.modal_price >= min_price)
        if max_price is not None:
            query = query.filter(MandiPriceRecord.modal_price <= max_price)

        total = query.count()
        safe_limit = max(1, min(limit, 100))
        safe_page = max(1, page)
        offset = (safe_page - 1) * safe_limit

        records = (
            query.order_by(
                desc(MandiPriceRecord.market_date),
                desc(MandiPriceRecord.fetched_at),
                MandiPriceRecord.market.asc(),
            )
            .offset(offset)
            .limit(safe_limit)
            .all()
        )

        items = [
            {
                "id": r.id,
                "commodity": r.commodity,
                "market": r.market,
                "district": r.district,
                "state": r.state,
                "min_price": r.min_price,
                "max_price": r.max_price,
                "modal_price": r.modal_price,
                "currency": r.currency,
                "unit": r.unit,
                "arrival_quantity": r.arrival_quantity,
                "arrival_unit": r.arrival_unit,
                "market_date": r.market_date,
                "source_name": r.source_name,
                "source_url": r.source_url,
                "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
                "verification_status": r.verification_status,
            }
            for r in records
        ]

        # Distinct sources representation
        sources_list = [
            s[0]
            for s in db.query(MandiPriceRecord.source_name).distinct().all()
            if s[0]
        ]

        return {
            "total": total,
            "page": safe_page,
            "limit": safe_limit,
            "has_more": offset + safe_limit < total,
            "records": items,
            "sources": sources_list,
            "last_updated": _LAST_SUCCESSFUL_REFRESH.isoformat() if _LAST_SUCCESSFUL_REFRESH else datetime.now().isoformat(),
        }

    @classmethod
    def get_commodity_prices(
        cls,
        db: Session,
        commodity: str,
        state: Optional[str] = None,
        district: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Retrieves price records for a specific commodity across markets."""
        return cls.get_prices(
            db,
            commodity=commodity,
            state=state,
            district=district,
            limit=limit,
        )

    @classmethod
    def get_districts(cls, db: Session, state: Optional[str] = None) -> List[str]:
        """Lists supported agricultural districts."""
        cls.ensure_seed_data(db)
        query = db.query(MandiPriceRecord.district).distinct()
        if state:
            query = query.filter(MandiPriceRecord.state.ilike(f"%{state.strip()}%"))
        results = [d[0] for d in query.all() if d[0]]

        # Also merge districts from MandiMarket directory
        mkt_query = db.query(MandiMarket.district).distinct()
        if state:
            mkt_query = mkt_query.filter(MandiMarket.state.ilike(f"%{state.strip()}%"))
        results.extend([d[0] for d in mkt_query.all() if d[0]])

        return sorted(list(set(results)))

    @classmethod
    def get_locations(cls, db: Session, state: Optional[str] = None, district: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists available APMC markets with district and state details."""
        cls.ensure_seed_data(db)
        query = db.query(MandiMarket)
        if state:
            query = query.filter(MandiMarket.state.ilike(f"%{state.strip()}%"))
        if district:
            query = query.filter(MandiMarket.district.ilike(f"%{district.strip()}%"))

        markets = query.order_by(MandiMarket.market_name.asc()).all()
        if not markets:
            # Fallback to distinct markets in mandi_prices
            p_query = db.query(MandiPriceRecord.market, MandiPriceRecord.district, MandiPriceRecord.state).distinct()
            if state:
                p_query = p_query.filter(MandiPriceRecord.state.ilike(f"%{state.strip()}%"))
            if district:
                p_query = p_query.filter(MandiPriceRecord.district.ilike(f"%{district.strip()}%"))
            return [
                {"market_name": m[0], "district": m[1], "state": m[2], "market_type": "Principal Yard"}
                for m in p_query.all()
            ]

        return [
            {
                "id": m.id,
                "market_name": m.market_name,
                "district": m.district,
                "state": m.state,
                "market_type": m.market_type,
            }
            for m in markets
        ]

    @classmethod
    def get_sources_info(cls, db: Session) -> Dict[str, Any]:
        """Provides transparency on data sources, total records per source, and last fetch timestamps."""
        cls.ensure_seed_data(db)
        sources_data = []

        distinct_sources = db.query(MandiPriceRecord.source_name).distinct().all()
        for s_tuple in distinct_sources:
            s_name = s_tuple[0]
            rec_count = db.query(MandiPriceRecord).filter(MandiPriceRecord.source_name == s_name).count()
            latest = (
                db.query(MandiPriceRecord.fetched_at)
                .filter(MandiPriceRecord.source_name == s_name)
                .order_by(desc(MandiPriceRecord.fetched_at))
                .first()
            )
            sources_data.append({
                "source_name": s_name,
                "record_count": rec_count,
                "last_fetched": latest[0].isoformat() if latest and latest[0] else None,
                "type": "official_government" if s_name in ("AGMARKNET", "e-NAM", "Karnataka APMC Portal") else "verified_market_feed"
            })

        return {
            "total_sources": len(sources_data),
            "sources": sources_data,
            "last_successful_refresh": _LAST_SUCCESSFUL_REFRESH.isoformat() if _LAST_SUCCESSFUL_REFRESH else None,
        }

    @classmethod
    async def refresh_market_data(cls, db: Session, actor: Optional[str] = "admin") -> Dict[str, Any]:
        """
        Executes a multi-source data refresh.
        Collects from preferred official sources first (AGMARKNET, e-NAM, Karnataka APMC),
        merges with benchmark reference feeds, validates, and stores results.
        """
        global _LAST_SUCCESSFUL_REFRESH
        start_time = datetime.now()
        collected_records: List[MandiPriceSchema] = []
        errors: List[str] = []

        # 1. Fetch from AGMARKNET
        try:
            ag_records = await AgmarknetSource.fetch_prices(state="Karnataka")
            collected_records.extend(ag_records)
        except Exception as exc:
            errors.append(f"AGMARKNET error: {exc}")

        # 2. Fetch from e-NAM
        try:
            enam_records = await EnamSource.fetch_prices(state="Karnataka")
            collected_records.extend(enam_records)
        except Exception as exc:
            errors.append(f"e-NAM error: {exc}")

        # 3. Fetch from Karnataka APMC portal
        try:
            kar_records = await KarnatakaApmcSource.fetch_prices()
            collected_records.extend(kar_records)
        except Exception as exc:
            errors.append(f"Karnataka APMC error: {exc}")

        # 4. Include verified benchmarks for core Karnataka mandis (Mandya, Mysuru, Maddur, etc.)
        ref_records = get_verified_reference_records()
        collected_records.extend(ref_records)

        # 5. Validate, detect conflicts, and persist
        saved_count = cls.save_records(db, collected_records)
        _LAST_SUCCESSFUL_REFRESH = datetime.now()

        audit_entry = {
            "timestamp": _LAST_SUCCESSFUL_REFRESH.isoformat(),
            "actor": actor,
            "records_processed": len(collected_records),
            "records_saved": saved_count,
            "errors": errors,
            "duration_secs": (datetime.now() - start_time).total_seconds(),
        }
        _REFRESH_AUDIT_LOGS.append(audit_entry)

        return {
            "status": "success",
            "message": f"Mandi markets data refresh completed. {saved_count} records processed.",
            "records_saved": saved_count,
            "audit": audit_entry,
        }
