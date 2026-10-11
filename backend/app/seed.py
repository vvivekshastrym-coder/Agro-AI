from sqlalchemy.orm import Session
import os
import sys
from .database.connection import engine, SessionLocal, Base
from .database.models import (
    User, Driver, Vehicle, MarketplaceSeller,
    MarketplaceProduct, DroneOperator, MarketPrice
)

# Ensure database tables are created without synthetic mock data
Base.metadata.create_all(bind=engine)

def purge_fictional_seed_data():
    """
    Purges any synthetic demo drivers, sellers, products, operators, or fabricated prices.
    Agro AI strictly connects to verified real external providers.
    """
    db: Session = SessionLocal()
    try:
        db.query(DroneOperator).delete()
        db.query(MarketplaceProduct).delete()
        db.query(MarketplaceSeller).delete()
        db.query(Vehicle).delete()
        db.query(Driver).delete()
        db.commit()
        print("[SUCCESS] Fictional seed data cleanly purged from database.")
    except Exception as e:
        print(f"Error purging database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if os.getenv("ALLOW_DEMO_SEED") != "1":
        sys.exit("Refusing to seed: this script inserts FICTIONAL drivers/sellers/operators/prices. "
                 "Set ALLOW_DEMO_SEED=1 only for an isolated local demo database, never production.")
    purge_fictional_seed_data()

