from sqlalchemy.orm import Session
import uuid
import datetime
from .database.connection import engine, SessionLocal, Base
from .database.models import (
    User, UserRole, Driver, Vehicle, VerificationStatus,
    MarketplaceSeller, MarketplaceProduct, DroneOperator, MarketPrice
)

Base.metadata.create_all(bind=engine)

def seed_database():
    db: Session = SessionLocal()
    try:
        # 1. Seed Verified Drivers & Vehicles for Logistics
        if db.query(Driver).count() == 0:
            user1 = User(
                id=str(uuid.uuid4()),
                phone="+919876543210",
                full_name="Ramesh Kumar",
                role=UserRole.driver,
                is_verified=True
            )
            db.add(user1)
            db.commit()

            driver1 = Driver(
                id=str(uuid.uuid4()),
                user_id=user1.id,
                driving_licence_number="KA-05-2021-009412",
                verification_status=VerificationStatus.verified,
                verified_at=datetime.datetime.utcnow(),
                is_online=True,
                current_lat=12.9716,
                current_lon=77.5946,
                rating=4.9,
                total_trips=142
            )
            db.add(driver1)
            db.commit()

            vehicle1 = Vehicle(
                id=str(uuid.uuid4()),
                driver_id=driver1.id,
                vehicle_type="Tata Ace",
                registration_number="KA-05-EA-8842",
                payload_capacity_tons=0.8,
                fuel_type="Diesel",
                fuel_efficiency_kmpl=15.0,
                insurance_status=VerificationStatus.verified,
                fitness_status=VerificationStatus.verified,
                permit_status=VerificationStatus.verified,
                rate_per_km=22.0,
                base_charge=350.0,
                is_active=True
            )
            db.add(vehicle1)
            
            # Add Second Verified Driver
            user2 = User(
                id=str(uuid.uuid4()),
                phone="+919876543211",
                full_name="Suresh Gowda",
                role=UserRole.driver,
                is_verified=True
            )
            db.add(user2)
            db.commit()

            driver2 = Driver(
                id=str(uuid.uuid4()),
                user_id=user2.id,
                driving_licence_number="KA-09-2019-001234",
                verification_status=VerificationStatus.verified,
                verified_at=datetime.datetime.utcnow(),
                is_online=True,
                current_lat=12.9800,
                current_lon=77.6000,
                rating=4.8,
                total_trips=98
            )
            db.add(driver2)
            db.commit()

            vehicle2 = Vehicle(
                id=str(uuid.uuid4()),
                driver_id=driver2.id,
                vehicle_type="Eicher",
                registration_number="KA-09-MC-4512",
                payload_capacity_tons=5.0,
                fuel_type="Diesel",
                fuel_efficiency_kmpl=8.0,
                insurance_status=VerificationStatus.verified,
                fitness_status=VerificationStatus.verified,
                permit_status=VerificationStatus.verified,
                rate_per_km=45.0,
                base_charge=1200.0,
                is_active=True
            )
            db.add(vehicle2)

        # 2. Seed Input Marketplace Sellers & Products
        if db.query(MarketplaceSeller).count() == 0:
            seller1 = MarketplaceSeller(
                id=str(uuid.uuid4()),
                name="Mandya Ryot Seva Kendra",
                seller_type="Authorized Dealer",
                license_number="KAR/MND/AGR/2022/410",
                district="Mandya",
                state="Karnataka",
                lat=12.5218,
                lon=76.8951,
                rating=4.9,
                is_verified=True
            )
            db.add(seller1)
            db.commit()

            p1 = MarketplaceProduct(
                id=str(uuid.uuid4()),
                seller_id=seller1.id,
                title="Neem Oil Organic Bio-Pesticide 10000 PPM",
                category="Pesticide",
                brand="Kisan Shield",
                pack_size="1 Liter",
                pack_size_value=1.0,
                mrp=650.0,
                current_price=520.0,
                in_stock=True,
                stock_count=45,
                delivery_charge=40.0,
                delivery_estimate_days=1,
                data_source="Direct Verified Partner API"
            )
            p2 = MarketplaceProduct(
                id=str(uuid.uuid4()),
                seller_id=seller1.id,
                title="Nano Urea Liquid Fertilizer",
                category="Fertilizer",
                brand="IFFCO",
                pack_size="500 ml",
                pack_size_value=0.5,
                mrp=240.0,
                current_price=225.0,
                in_stock=True,
                stock_count=120,
                delivery_charge=30.0,
                delivery_estimate_days=1,
                data_source="Direct Verified Partner API"
            )
            p3 = MarketplaceProduct(
                id=str(uuid.uuid4()),
                seller_id=seller1.id,
                title="Copper Oxychloride 50% WP Fungicide",
                category="Pesticide",
                brand="Tata Rallis",
                pack_size="500 grams",
                pack_size_value=0.5,
                mrp=380.0,
                current_price=340.0,
                in_stock=True,
                stock_count=28,
                delivery_charge=40.0,
                delivery_estimate_days=2,
                data_source="Direct Verified Partner API"
            )
            db.add_all([p1, p2, p3])

        # 3. Seed Drone Operators
        if db.query(DroneOperator).count() == 0:
            d1 = DroneOperator(
                id=str(uuid.uuid4()),
                name="Kisan Drone Aero Services",
                company="AgriFly Technologies India",
                dgca_registration="DGCA-UAV-2023-9081",
                is_verified=True,
                lat=12.9716,
                lon=77.5946,
                drone_model="DJI Agras T40 Precision Sprayer",
                rate_per_acre=350.0,
                min_booking_charge=1000.0,
                travel_charge_per_km=12.0,
                available_today=True,
                contact_phone="+919812345678",
                rating=4.9
            )
            db.add(d1)

        # 4. Seed Mandi Prices
        if db.query(MarketPrice).count() == 0:
            m1 = MarketPrice(
                id=str(uuid.uuid4()),
                commodity="Tomato",
                variety="Hybrid",
                market_name="Mandya Mandi",
                district="Mandya",
                state="Karnataka",
                min_price=1200.0,
                max_price=1800.0,
                modal_price=1500.0,
                unit="quintal",
                price_date=datetime.datetime.utcnow(),
                data_source="Agmarknet Govt Mandi Portal"
            )
            m2 = MarketPrice(
                id=str(uuid.uuid4()),
                commodity="Potato",
                variety="Jyoti",
                market_name="Hassan Mandi",
                district="Hassan",
                state="Karnataka",
                min_price=1400.0,
                max_price=2100.0,
                modal_price=1750.0,
                unit="quintal",
                price_date=datetime.datetime.utcnow(),
                data_source="Agmarknet Govt Mandi Portal"
            )
            db.add_all([m1, m2])

        db.commit()
        print("[SUCCESS] Database successfully seeded with verified initial data!")
    except Exception as e:
        print(f"Error seeding DB: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
