"""Data validation, schema enforcement, duplicate detection, and conflict flagging for Mandi Market prices."""
from datetime import datetime, date
import re
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator


class MandiPriceSchema(BaseModel):
    """Pydantic schema enforcing the exact required structured JSON representation."""
    commodity: str = Field(..., min_length=2, max_length=100)
    market: str = Field(..., min_length=2, max_length=150)
    district: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    min_price: float = Field(..., ge=0)
    max_price: float = Field(..., ge=0)
    modal_price: float = Field(..., ge=0)
    currency: str = Field(default="INR", max_length=10)
    unit: str = Field(default="quintal", max_length=20)
    arrival_quantity: Optional[float] = Field(default=None, ge=0)
    arrival_unit: Optional[str] = Field(default="quintal", max_length=20)
    market_date: str = Field(...)  # YYYY-MM-DD
    source_name: str = Field(default="AGMARKNET", min_length=2, max_length=100)
    source_url: Optional[str] = Field(default=None, max_length=500)
    fetched_at: Optional[str] = Field(default=None)
    verification_status: str = Field(default="verified")  # verified | provisional | flagged_conflict

    @field_validator("commodity", "market", "district", "state", mode="before")
    @classmethod
    def clean_strings(cls, v: Any) -> str:
        if not v or not str(v).strip():
            raise ValueError("Field must not be empty")
        return str(v).strip()

    @field_validator("market_date", mode="before")
    @classmethod
    def validate_market_date(cls, v: Any) -> str:
        if isinstance(v, (datetime, date)):
            d_str = v.strftime("%Y-%m-%d")
        else:
            d_str = str(v).strip()
        # Enforce YYYY-MM-DD format
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", d_str):
            raise ValueError(f"Invalid market_date format '{d_str}'; must be YYYY-MM-DD")
        try:
            parsed = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"Invalid calendar date '{d_str}'")
        # Check that market date is not in the future
        today = datetime.now().date()
        if parsed > today:
            raise ValueError(f"market_date '{d_str}' cannot be in the future (today is {today})")
        return d_str

    @field_validator("unit", "arrival_unit", mode="before")
    @classmethod
    def normalize_unit(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        cleaned = str(v).strip().lower()
        if cleaned in ("quintal", "qtl", "qntl", "rs/quintal", "rs./qtl", "rs/qtl"):
            return "quintal"
        if cleaned in ("kg", "kilogram", "kgs"):
            return "kg"
        if cleaned in ("ton", "tonne", "mt"):
            return "ton"
        return cleaned

    @model_validator(mode="after")
    def validate_price_bounds(self) -> "MandiPriceSchema":
        # Rule 3: Minimum price must not exceed maximum price
        if self.min_price > self.max_price:
            raise ValueError(f"min_price ({self.min_price}) cannot exceed max_price ({self.max_price})")
        # Ensure modal price is within reasonable bounds of [min, max] or flagged
        if self.modal_price < self.min_price or self.modal_price > self.max_price:
            # If modal price is outside [min, max], adjust verification status to provisional
            if self.verification_status == "verified":
                self.verification_status = "provisional"
        if not self.fetched_at:
            self.fetched_at = datetime.now().isoformat()
        return self


MandiPriceRecordDTO = MandiPriceSchema


def validate_raw_market_entry(entry: Dict[str, Any]) -> Tuple[Optional[MandiPriceSchema], Optional[str]]:
    """Validates a raw dictionary against all 10 Mandi market validation rules."""
    try:
        validated = MandiPriceSchema(**entry)
        return validated, None
    except Exception as exc:
        return None, str(exc)


def detect_and_resolve_conflicts(records: List[MandiPriceSchema]) -> List[MandiPriceSchema]:
    """
    Detects duplicates and flags conflicting price observations across multiple sources.
    If multiple sources report for the same (commodity, market, market_date, unit) with differing modal prices,
    both records are preserved and tagged with verification_status = 'flagged_conflict'.
    """
    grouped: Dict[Tuple[str, str, str, str], List[MandiPriceSchema]] = {}
    for r in records:
        key = (
            r.commodity.strip().lower(),
            r.market.strip().lower(),
            r.market_date,
            r.unit.lower(),
        )
        grouped.setdefault(key, []).append(r)

    resolved: List[MandiPriceSchema] = []
    seen_unique: set = set()

    for key, items in grouped.items():
        # Check if multiple sources report differing modal prices
        if len(items) > 1:
            sources = {item.source_name for item in items}
            modal_prices = {item.modal_price for item in items}
            has_conflict = len(sources) > 1 and len(modal_prices) > 1

            for item in items:
                dedup_key = (
                    item.commodity.strip().lower(),
                    item.market.strip().lower(),
                    item.market_date,
                    item.unit.lower(),
                    item.source_name.strip().lower()
                )
                if dedup_key in seen_unique:
                    continue  # deduplicate exact identical source reports
                seen_unique.add(dedup_key)

                if has_conflict:
                    item.verification_status = "flagged_conflict"
                resolved.append(item)
        else:
            item = items[0]
            dedup_key = (
                item.commodity.strip().lower(),
                item.market.strip().lower(),
                item.market_date,
                item.unit.lower(),
                item.source_name.strip().lower()
            )
            if dedup_key not in seen_unique:
                seen_unique.add(dedup_key)
                resolved.append(item)

    return resolved
