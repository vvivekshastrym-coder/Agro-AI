"""Automated scheduler and background worker for daily Mandi market data updates."""
import asyncio
import datetime
import logging
from typing import Optional

from ...database.connection import SessionLocal
from .market_service import MandiMarketService

logger = logging.getLogger(__name__)

_SCHEDULER_RUNNING = False
_LAST_DAILY_RUN: Optional[datetime.date] = None


async def run_daily_market_update_job(max_retries: int = 3, base_backoff_secs: float = 2.0) -> dict:
    """
    Executes daily market price update with exponential backoff retry for transient network errors.
    """
    db = SessionLocal()
    attempt = 0
    last_error = None

    while attempt < max_retries:
        attempt += 1
        try:
            logger.info("Executing daily Mandi market data collection (attempt %d/%d)...", attempt, max_retries)
            result = await MandiMarketService.refresh_market_data(db, actor="scheduler:daily_cron")
            db.close()
            return result
        except Exception as exc:
            last_error = exc
            logger.warning("Mandi update job attempt %d failed: %s", attempt, exc)
            if attempt < max_retries:
                backoff = base_backoff_secs * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)

    db.close()
    logger.error("Daily Mandi update job failed after %d retries: %s", max_retries, last_error)
    return {
        "status": "error",
        "message": f"Daily update failed after {max_retries} attempts: {last_error}",
        "records_saved": 0,
    }


async def market_scheduler_loop(interval_hours: int = 6):
    """Standing background worker checking and running market updates periodically."""
    global _SCHEDULER_RUNNING, _LAST_DAILY_RUN
    if _SCHEDULER_RUNNING:
        return
    _SCHEDULER_RUNNING = True
    logger.info("Mandi Market background update scheduler started (interval: %d hours).", interval_hours)

    while _SCHEDULER_RUNNING:
        try:
            today = datetime.date.today()
            if _LAST_DAILY_RUN != today:
                res = await run_daily_market_update_job()
                if res.get("status") == "success":
                    _LAST_DAILY_RUN = today
        except Exception as exc:
            logger.error("Error in market scheduler loop: %s", exc)

        # Sleep for interval
        await asyncio.sleep(interval_hours * 3600)
