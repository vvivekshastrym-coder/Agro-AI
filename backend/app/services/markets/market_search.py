"""Search and discovery service for daily mandi prices across verified agricultural portals."""
import datetime
import logging
import urllib.parse
from typing import List, Optional, Dict, Any

from .market_scraper import fetch_market_url, is_safe_url
from .market_parser import parse_html_table_prices
from .market_validator import MandiPriceSchema, validate_raw_market_entry

logger = logging.getLogger(__name__)


def build_search_queries(
    commodity: str,
    market: str,
    district: str,
    state: str = "Karnataka",
    market_date: Optional[str] = None,
) -> List[str]:
    """Generates standard search combinations for official mandi price discovery."""
    date_str = market_date or datetime.date.today().strftime("%Y-%m-%d")
    return [
        f"{commodity} {market} {district} {state} mandi price {date_str}",
        f"{market} APMC {commodity} daily arrival rate {date_str}",
        f"{state} APMC market price {commodity} {district}",
    ]


async def discover_and_extract_prices(
    commodity: str,
    market: str,
    district: str,
    state: str = "Karnataka",
    target_url: Optional[str] = None,
) -> List[MandiPriceSchema]:
    """
    Discovers and extracts commodity prices from original source pages.
    Never relies on unverified search snippets: opens and parses the original page directly.
    """
    discovered_records: List[MandiPriceSchema] = []

    # If an original target source URL is provided or discovered:
    if target_url and is_safe_url(target_url):
        content = await fetch_market_url(target_url)
        if content:
            parsed_entries = parse_html_table_prices(content, default_state=state, source_url=target_url)
            for entry in parsed_entries:
                if commodity.lower() in entry["commodity"].lower():
                    entry["market"] = market or entry["market"]
                    entry["district"] = district or entry["district"]
                    validated, err = validate_raw_market_entry(entry)
                    if validated:
                        discovered_records.append(validated)

    return discovered_records
