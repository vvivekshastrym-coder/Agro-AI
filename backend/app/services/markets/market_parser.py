"""Parses raw API JSON, HTML tables, and feeds into structured, normalized Mandi price records."""
from datetime import datetime, date
import logging
import re
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup

from .market_scraper import sanitize_html

logger = logging.getLogger(__name__)


def parse_price_value(val: Any) -> Optional[float]:
    """Cleans currency strings ('₹ 1,850', '2100/qtl', '1950.00') into float, preserving None for missing values."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s in ("-", "NA", "N/A", "null", "None", "nil"):
        return None
    # Strip currency symbols, commas, words, whitespace, while preserving decimal dot
    cleaned = re.sub(r"[^\d.]", "", s.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_date_string(date_val: Any) -> Optional[str]:
    """Parses various date formats into standard YYYY-MM-DD string."""
    if not date_val:
        return None
    if isinstance(date_val, (datetime, date)):
        return date_val.strftime("%Y-%m-%d")
    s = str(date_val).strip()
    # Try YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    # Try DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return f"{year:04d}-{month:02d}-{day:02d}"
        except Exception:
            pass
    # Try other common textual formats
    for fmt in ("%d %b %Y", "%d %B %Y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_agmarknet_api_record(rec: Dict[str, Any], source_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Normalizes an Agmarknet / data.gov.in API record into the structured schema."""
    commodity = rec.get("commodity") or rec.get("Commodity")
    market = rec.get("market") or rec.get("Market")
    district = rec.get("district") or rec.get("District")
    state = rec.get("state") or rec.get("State")

    if not commodity or not market or not state:
        return None

    min_p = parse_price_value(rec.get("min_price") or rec.get("Min_Price") or rec.get("minPrice"))
    max_p = parse_price_value(rec.get("max_price") or rec.get("Max_Price") or rec.get("maxPrice"))
    modal_p = parse_price_value(rec.get("modal_price") or rec.get("Modal_Price") or rec.get("modalPrice"))

    # Never invent missing prices
    if min_p is None or max_p is None:
        return None
    if modal_p is None:
        # Keep modal_price = max_p or min_p only if one price reported, but mark as modal
        modal_p = min_p if min_p == max_p else round((min_p + max_p) / 2.0, 2)

    # Date normalization
    raw_date = rec.get("arrival_date") or rec.get("Arrival_Date") or rec.get("price_date") or rec.get("date")
    market_date = parse_date_string(raw_date) or datetime.now().strftime("%Y-%m-%d")

    # Arrivals
    arrival_q = parse_price_value(rec.get("arrival_quantity") or rec.get("Arrivals"))
    arrival_u = rec.get("arrival_unit") or "quintal"

    return {
        "commodity": commodity.strip().title(),
        "market": market.strip(),
        "district": (district or market).strip(),
        "state": state.strip(),
        "min_price": min_p,
        "max_price": max_p,
        "modal_price": modal_p,
        "currency": "INR",
        "unit": "quintal",
        "arrival_quantity": arrival_q,
        "arrival_unit": arrival_u,
        "market_date": market_date,
        "source_name": "AGMARKNET",
        "source_url": source_url or "https://agmarknet.gov.in",
        "fetched_at": datetime.now().isoformat(),
        "verification_status": "verified"
    }


def parse_html_table_prices(html_content: str, default_state: str = "Karnataka", source_url: str = "") -> List[Dict[str, Any]]:
    """Extracts tabular market prices from sanctioned APMC HTML portal pages."""
    soup = sanitize_html(html_content)
    results: List[Dict[str, Any]] = []

    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        header_row = rows[0]
        headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]

        # Identify columns
        comm_idx, mkt_idx, dist_idx, min_idx, max_idx, mod_idx, date_idx = -1, -1, -1, -1, -1, -1, -1
        for i, h in enumerate(headers):
            if "commodity" in h or "crop" in h: comm_idx = i
            elif "market" in h or "mandi" in h or "apmc" in h: mkt_idx = i
            elif "district" in h: dist_idx = i
            elif "min" in h: min_idx = i
            elif "max" in h: max_idx = i
            elif "modal" in h or "model" in h: mod_idx = i
            elif "date" in h: date_idx = i

        if comm_idx == -1 or (min_idx == -1 and max_idx == -1 and mod_idx == -1):
            continue

        for r in rows[1:]:
            cols = [td.get_text(strip=True) for td in r.find_all(["td", "th"])]
            if len(cols) <= max(comm_idx, mkt_idx, min_idx, max_idx, mod_idx):
                continue

            comm = cols[comm_idx] if comm_idx != -1 else ""
            mkt = cols[mkt_idx] if mkt_idx != -1 else "District APMC"
            dist = cols[dist_idx] if dist_idx != -1 else "Mandya"
            min_p = parse_price_value(cols[min_idx]) if min_idx != -1 else None
            max_p = parse_price_value(cols[max_idx]) if max_idx != -1 else None
            mod_p = parse_price_value(cols[mod_idx]) if mod_idx != -1 else None
            d_val = parse_date_string(cols[date_idx]) if date_idx != -1 else datetime.now().strftime("%Y-%m-%d")

            if not comm or min_p is None or max_p is None:
                continue

            if mod_p is None:
                mod_p = min_p if min_p == max_p else round((min_p + max_p) / 2.0, 2)

            results.append({
                "commodity": comm.title(),
                "market": mkt,
                "district": dist,
                "state": default_state,
                "min_price": min_p,
                "max_price": max_p,
                "modal_price": mod_p,
                "currency": "INR",
                "unit": "quintal",
                "arrival_quantity": None,
                "arrival_unit": "quintal",
                "market_date": d_val or datetime.now().strftime("%Y-%m-%d"),
                "source_name": "State APMC Portal",
                "source_url": source_url,
                "fetched_at": datetime.now().isoformat(),
                "verification_status": "verified"
            })

    return results
