from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from .connection import Base
import enum


class UserRole(str, enum.Enum):
    farmer = 'farmer'
    driver = 'driver'
    expert = 'expert'
    admin = 'admin'


class VerificationStatus(str, enum.Enum):
    pending = 'pending'
    verified = 'verified'
    rejected = 'rejected'
    suspended = 'suspended'
    expired = 'expired'


class TripStatus(str, enum.Enum):
    REQUESTED = 'REQUESTED'
    MATCHING = 'MATCHING'
    DRIVER_ASSIGNED = 'DRIVER_ASSIGNED'
    DRIVER_EN_ROUTE = 'DRIVER_EN_ROUTE'
    ARRIVED = 'ARRIVED'
    LOADING = 'LOADING'
    IN_TRANSIT = 'IN_TRANSIT'
    ARRIVED_DESTINATION = 'ARRIVED_DESTINATION'
    UNLOADING = 'UNLOADING'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'
    DISPUTED = 'DISPUTED'


class User(Base):
    """Primary user account — farmers, drivers, experts, and admins."""
    __tablename__ = 'users'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    phone = Column(String(15), unique=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    full_name = Column(String(100))
    role = Column(Enum(UserRole), default=UserRole.farmer)
    preferred_language = Column(String(10), default='en')
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_test = Column(Boolean, default=False, nullable=False)
    avatar_url = Column(String(500), nullable=True)
    fcm_token = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    farm = relationship('Farm', back_populates='user', uselist=False)
    sessions = relationship('UserSession', back_populates='user')
    diagnosis_reports = relationship('DiagnosisReport', back_populates='user')
    driver_profile = relationship('Driver', back_populates='user', uselist=False)


class Farm(Base):
    """Farm details associated with a user account."""
    __tablename__ = 'farms'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'))
    village = Column(String(100))
    district = Column(String(100))
    state = Column(String(100))
    pincode = Column(String(10))
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    total_acres = Column(Float)
    owned_acres = Column(Float)
    leased_acres = Column(Float, default=0)
    gps_boundary = Column(JSON, nullable=True)
    irrigation_method = Column(String(50), nullable=True)
    soil_type = Column(String(50), nullable=True)
    water_source = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship('User', back_populates='farm')
    fields = relationship('Field', back_populates='farm')
    crops = relationship('FarmCrop', back_populates='farm')


class Field(Base):
    """Individual field/plot within a farm."""
    __tablename__ = 'fields'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id = Column(String, ForeignKey('farms.id', ondelete='CASCADE'))
    name = Column(String(100))
    area_acres = Column(Float)
    current_crop = Column(String(100), nullable=True)
    soil_type = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    farm = relationship('Farm', back_populates='fields')


class FarmCrop(Base):
    """Individual crop records within a farm."""
    __tablename__ = 'farm_crops'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id = Column(String, ForeignKey('farms.id', ondelete='CASCADE'))
    crop_name = Column(String(100))
    crop_variety = Column(String(100), nullable=True)
    season = Column(String(50))
    sown_date = Column(DateTime(timezone=True), nullable=True)
    expected_harvest_date = Column(DateTime(timezone=True), nullable=True)
    area_acres = Column(Float)
    expected_yield = Column(Float, nullable=True)
    actual_yield = Column(Float, nullable=True)
    input_cost = Column(Float, nullable=True)
    selling_price = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    farm = relationship('Farm', back_populates='crops')


class DiagnosisReport(Base):
    """AI-generated crop disease diagnosis reports."""
    __tablename__ = 'diagnosis_reports'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    farmer_id = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    farm_id = Column(String, ForeignKey('farms.id', ondelete='SET NULL'), nullable=True)
    field_id = Column(String, ForeignKey('fields.id', ondelete='SET NULL'), nullable=True)
    image_url = Column(String(500))
    crop = Column(String(100))
    disease = Column(String(200))
    scientific_name = Column(String(200), nullable=True)
    confidence = Column(Float)
    severity = Column(String(50))           # healthy | mild | moderate | critical
    evidence = Column(JSON, default=list)
    organic_treatment = Column(JSON, default=list)
    chemical_treatment = Column(JSON, default=list)
    dosage = Column(JSON, default=list)
    prevention = Column(JSON, default=list)
    spray_window = Column(String(200), nullable=True)
    expected_recovery_days = Column(Integer, nullable=True)
    warnings = Column(JSON, default=list)
    model = Column(String(100), default='gemini-2.0-flash')
    model_version = Column(String(20), default='1.0')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship('User', back_populates='diagnosis_reports')
    images = relationship('DiagnosisImage', back_populates='report')


class DiagnosisImage(Base):
    """Uploaded leaf diagnosis images."""
    __tablename__ = 'diagnosis_images'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String, ForeignKey('diagnosis_reports.id', ondelete='CASCADE'))
    file_path = Column(String(500))
    file_size_bytes = Column(Integer)
    mime_type = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    report = relationship('DiagnosisReport', back_populates='images')


class AgroGPTConversation(Base):
    """Agro GPT chat conversations."""
    __tablename__ = 'agro_gpt_conversations'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    farmer_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), index=True)
    title = Column(String(200), default='Farm Assistant Chat')
    language = Column(String(10), default='en')
    context_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    messages = relationship('AgroGPTMessage', back_populates='conversation', cascade='all, delete-orphan')


class AgroGPTMessage(Base):
    """Individual Agro GPT messages."""
    __tablename__ = 'agro_gpt_messages'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey('agro_gpt_conversations.id', ondelete='CASCADE'), index=True)
    role = Column(String(20))               # user | assistant | system
    content = Column(Text)
    language = Column(String(10), default='en')
    context_references = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship('AgroGPTConversation', back_populates='messages')


class AIContext(Base):
    """Aggregated farmer context stored for AI retrieval."""
    __tablename__ = 'ai_context'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    farmer_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), index=True)
    active_diagnosis_id = Column(String, nullable=True)
    last_known_lat = Column(Float, nullable=True)
    last_known_lon = Column(Float, nullable=True)
    context_json = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AIUsage(Base):
    """Token & cost tracking for AI models."""
    __tablename__ = 'ai_usage'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    farmer_id = Column(String, nullable=True, index=True)
    provider = Column(String(50))
    model = Column(String(100))
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    latency_ms = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class APILog(Base):
    """Structured request logging without keys."""
    __tablename__ = 'api_logs'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String(100), index=True)
    user_id = Column(String, nullable=True, index=True)
    endpoint = Column(String(200))
    provider = Column(String(50), nullable=True)
    model = Column(String(100), nullable=True)
    latency_ms = Column(Float)
    status_code = Column(Integer)
    error_code = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Driver(Base):
    """Verified transport drivers for Agro AI Logistics."""
    __tablename__ = 'drivers'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), index=True)
    driving_licence_number = Column(String(50))
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.pending)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    document_expiry = Column(DateTime(timezone=True), nullable=True)
    verification_provider = Column(String(100), default='GovKYC_Verified')
    verification_reference = Column(String(100), nullable=True)
    bank_upi_id = Column(String(100), nullable=True)
    emergency_contact = Column(String(15), nullable=True)
    is_online = Column(Boolean, default=False)
    is_busy = Column(Boolean, default=False)
    current_lat = Column(Float, nullable=True)
    current_lon = Column(Float, nullable=True)
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    rating = Column(Float, default=5.0)
    total_trips = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship('User', back_populates='driver_profile')
    vehicles = relationship('Vehicle', back_populates='driver')
    trips = relationship('LogisticsTrip', back_populates='driver')


class Vehicle(Base):
    """Agricultural transport vehicles."""
    __tablename__ = 'vehicles'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    driver_id = Column(String, ForeignKey('drivers.id', ondelete='CASCADE'))
    vehicle_type = Column(String(50))        # Mini Truck | Tata Ace | Eicher | Tata 407 | Tractor Trailer | etc.
    registration_number = Column(String(30), unique=True)
    payload_capacity_tons = Column(Float)
    fuel_type = Column(String(20), default='Diesel')
    fuel_efficiency_kmpl = Column(Float, default=10.0)
    insurance_status = Column(Enum(VerificationStatus), default=VerificationStatus.verified)
    fitness_status = Column(Enum(VerificationStatus), default=VerificationStatus.verified)
    permit_status = Column(Enum(VerificationStatus), default=VerificationStatus.verified)
    rate_per_km = Column(Float, default=35.0)
    base_charge = Column(Float, default=500.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    driver = relationship('Driver', back_populates='vehicles')


class LogisticsTrip(Base):
    """Agricultural transportation trips."""
    __tablename__ = 'logistics_trips'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    farmer_id = Column(String, ForeignKey('users.id', ondelete='SET NULL'), index=True)
    driver_id = Column(String, ForeignKey('drivers.id', ondelete='SET NULL'), nullable=True, index=True)
    vehicle_id = Column(String, ForeignKey('vehicles.id', ondelete='SET NULL'), nullable=True)
    status = Column(Enum(TripStatus), default=TripStatus.REQUESTED)
    crop_type = Column(String(100))
    quantity_tons = Column(Float)
    pickup_address = Column(String(255))
    pickup_lat = Column(Float)
    pickup_lon = Column(Float)
    dest_address = Column(String(255))
    dest_lat = Column(Float)
    dest_lon = Column(Float)
    distance_km = Column(Float)
    estimated_duration_mins = Column(Integer)
    base_fare = Column(Float)
    distance_fare = Column(Float)
    fuel_component = Column(Float)
    toll_estimate = Column(Float, default=0.0)
    loading_charge = Column(Float, default=200.0)
    unloading_charge = Column(Float, default=200.0)
    platform_fee = Column(Float, default=50.0)
    total_price = Column(Float)
    driver_net_earnings = Column(Float)
    pickup_time = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_reason = Column(String(255), nullable=True)
    rating_by_farmer = Column(Float, nullable=True)
    review_by_farmer = Column(Text, nullable=True)
    routing_source = Column(String(100), default='OpenStreetMap OSRM / Haversine (Real Routing)')
    trip_pin = Column(String(6), nullable=True)              # 6-digit PIN for trip verification
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    driver_arrived_at = Column(DateTime(timezone=True), nullable=True)
    sos_triggered = Column(Boolean, default=False)
    share_token = Column(String(64), nullable=True)          # for public trip tracking link
    polyline = Column(Text, nullable=True)                   # encoded Google Maps polyline
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    driver = relationship('Driver', back_populates='trips')
    farmer = relationship('User', foreign_keys='LogisticsTrip.farmer_id')
    events = relationship('TripEvent', back_populates='trip', order_by='TripEvent.created_at')
    locations = relationship('DriverLocation', back_populates='trip', order_by='DriverLocation.recorded_at')


class DriverLocation(Base):
    """Real-time GPS location history for drivers during active trips."""
    __tablename__ = 'driver_locations'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    driver_id = Column(String, ForeignKey('drivers.id', ondelete='CASCADE'), index=True)
    trip_id = Column(String, ForeignKey('logistics_trips.id', ondelete='CASCADE'), nullable=True, index=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    accuracy_m = Column(Float, nullable=True)       # GPS accuracy in metres
    heading_deg = Column(Float, nullable=True)      # compass heading 0-360
    speed_kmh = Column(Float, nullable=True)        # speed in km/h
    altitude_m = Column(Float, nullable=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    driver = relationship('Driver')
    trip = relationship('LogisticsTrip', back_populates='locations')


class TripEvent(Base):
    """State machine event log for every trip status change."""
    __tablename__ = 'trip_events'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id = Column(String, ForeignKey('logistics_trips.id', ondelete='CASCADE'), index=True)
    actor_id = Column(String, nullable=True)        # user_id or driver user_id who triggered the event
    actor_role = Column(String(20), nullable=True)  # 'farmer' | 'driver' | 'system'
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=False)
    note = Column(String(500), nullable=True)
    lat = Column(Float, nullable=True)              # location when event fired
    lon = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip = relationship('LogisticsTrip', back_populates='events')


class DriverDocument(Base):
    """KYC / licence / vehicle documents uploaded by drivers for verification."""
    __tablename__ = 'driver_documents'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    driver_id = Column(String, ForeignKey('drivers.id', ondelete='CASCADE'), index=True)
    doc_type = Column(String(50))   # 'DRIVING_LICENCE' | 'AADHAAR' | 'PAN' | 'RC_BOOK' | 'INSURANCE' | 'FITNESS' | 'PERMIT'
    doc_number = Column(String(100), nullable=True)
    file_path = Column(String(500), nullable=True)  # server-side storage path
    file_url = Column(String(500), nullable=True)   # public URL if cloud-stored
    issued_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.pending)
    rejection_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    driver = relationship('Driver')


class FareCalculation(Base):
    """Detailed fare breakdown stored per trip for audit and disputes."""
    __tablename__ = 'fare_calculations'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id = Column(String, ForeignKey('logistics_trips.id', ondelete='CASCADE'), unique=True, index=True)
    distance_km = Column(Float)
    duration_mins = Column(Integer)
    routing_source = Column(String(100))   # 'GoogleMaps' | 'OSRM' | 'Haversine'
    base_fare = Column(Float)
    distance_fare = Column(Float)
    fuel_cost = Column(Float)
    fuel_price_per_liter = Column(Float)
    fuel_liters = Column(Float)
    toll_estimate = Column(Float, default=0.0)
    loading_charge = Column(Float, default=200.0)
    unloading_charge = Column(Float, default=200.0)
    platform_fee = Column(Float, default=50.0)
    surge_multiplier = Column(Float, default=1.0)
    total_farmer_price = Column(Float)
    driver_net_earnings = Column(Float)
    price_per_quintal = Column(Float, nullable=True)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())


class MarketplaceSeller(Base):
    """Verified input marketplace sellers."""
    __tablename__ = 'marketplace_sellers'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150))
    seller_type = Column(String(50))        # Authorized Dealer | Krishi Kendra | Co-operative
    license_number = Column(String(100))
    district = Column(String(100))
    state = Column(String(100))
    lat = Column(Float)
    lon = Column(Float)
    rating = Column(Float, default=4.8)
    is_verified = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    products = relationship('MarketplaceProduct', back_populates='seller')


class MarketplaceProduct(Base):
    """Genuine agricultural input products."""
    __tablename__ = 'marketplace_products'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    seller_id = Column(String, ForeignKey('marketplace_sellers.id', ondelete='CASCADE'))
    title = Column(String(200))
    category = Column(String(50))           # Fertilizer | Pesticide | Seed | Equipment
    brand = Column(String(100))
    pack_size = Column(String(50))
    pack_size_value = Column(Float, default=1.0) # Numerical size in kg/litre
    mrp = Column(Float)
    current_price = Column(Float)
    in_stock = Column(Boolean, default=True)
    stock_count = Column(Integer, nullable=True)
    delivery_charge = Column(Float, default=50.0)
    delivery_estimate_days = Column(Integer, default=2)
    data_source = Column(String(100), default='Direct Verified Partner API')
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    seller = relationship('MarketplaceSeller', back_populates='products')


class DroneOperator(Base):
    """Verified agricultural drone scout operators."""
    __tablename__ = 'drone_operators'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150))
    company = Column(String(150))
    dgca_registration = Column(String(100))
    is_verified = Column(Boolean, default=True)
    lat = Column(Float)
    lon = Column(Float)
    drone_model = Column(String(100))
    rate_per_acre = Column(Float)
    min_booking_charge = Column(Float)
    travel_charge_per_km = Column(Float, default=10.0)
    available_today = Column(Boolean, default=True)
    contact_phone = Column(String(15))
    rating = Column(Float, default=4.9)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserSession(Base):
    """JWT refresh token sessions for multi-device support."""
    __tablename__ = 'user_sessions'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), index=True)
    refresh_token = Column(String(500))
    device_info = Column(String(255), nullable=True)
    ip_address = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship('User', back_populates='sessions')


class CarbonCredit(Base):
    """Carbon offset credits earned by farmers for sustainable practices."""
    __tablename__ = 'carbon_credits'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), index=True)
    tonnes_offset = Column(Float)
    status = Column(String(50))          # pending | verified | paid
    blockchain_hash = Column(String(200), nullable=True)
    payout_amount = Column(Float, nullable=True)
    payout_upi = Column(String(100), nullable=True)
    verification_agency = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    verified_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)


class MarketPrice(Base):
    """Mandi / market commodity prices aggregated daily."""
    __tablename__ = 'market_prices'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    commodity = Column(String(100), index=True)
    variety = Column(String(100), nullable=True)
    market_name = Column(String(150))
    state = Column(String(100))
    district = Column(String(100))
    min_price = Column(Float)
    max_price = Column(Float)
    modal_price = Column(Float)
    unit = Column(String(20), default='quintal')
    price_date = Column(DateTime(timezone=True), index=True)
    data_source = Column(String(100), default='Agmarknet / Govt Mandi Data API')
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WeatherCache(Base):
    """Cached weather API responses."""
    __tablename__ = 'weather_cache'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pincode = Column(String(10), index=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    data = Column(JSON)
    data_source = Column(String(100), default='OpenWeatherMap Live API')
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))


# ── PHASE 1: ADMIN, SUBSCRIPTIONS, ENTITLEMENTS & PAYMENTS ──────

class AdminUserRole(str, enum.Enum):
    super_admin = 'super_admin'
    listing_reviewer = 'listing_reviewer'
    seller_reviewer = 'seller_reviewer'
    plan_manager = 'plan_manager'
    payment_manager = 'payment_manager'
    payment_staff = 'payment_staff'
    support_agent = 'support_agent'
    content_manager = 'content_manager'
    analyst = 'analyst'


class FeatureState(str, enum.Enum):
    enabled = 'enabled'
    disabled = 'disabled'
    maintenance = 'maintenance'
    not_configured = 'not_configured'


class PlatformFeature(Base):
    __tablename__ = 'platform_features'

    key = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    state = Column(String(20), default='disabled', nullable=False) # enabled, disabled, maintenance, not_configured
    implemented = Column(Boolean, default=True, nullable=False)
    config = Column(JSON, default=dict, nullable=False)
    revision = Column(Integer, default=1, nullable=False)
    changed_by = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    reason = Column(Text, nullable=True)

    changer = relationship('User')


class PlatformFeatureHistory(Base):
    __tablename__ = 'platform_feature_history'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    feature_key = Column(String(50), nullable=False, index=True)
    state = Column(String(20), nullable=False)
    config = Column(JSON, nullable=False)
    revision = Column(Integer, nullable=False)
    changed_by = Column(String, nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    reason = Column(Text, nullable=True)


class AdminUser(Base):
    __tablename__ = 'admin_users'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), unique=True, index=True)
    role = Column(Enum(AdminUserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship('User')


class AdminAccessRequest(Base):
    """Queue for staff members requesting access to the Agro AI admin panel."""
    __tablename__ = 'admin_access_requests'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=False)
    requested_role = Column(String(50), default='support_agent', nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String(20), default='pending', nullable=False) # pending, approved, rejected
    reviewed_by = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship('User', foreign_keys=[user_id])
    reviewer = relationship('User', foreign_keys=[reviewed_by])


class SubscriptionPlan(Base):
    __tablename__ = 'subscription_plans'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(20), default='draft', nullable=False) # draft, published, paused, archived
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    versions = relationship('SubscriptionPlanVersion', back_populates='plan', cascade='all, delete-orphan')


class SubscriptionPlanVersion(Base):
    __tablename__ = 'subscription_plan_versions'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String, ForeignKey('subscription_plans.id', ondelete='CASCADE'), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price_minor = Column(Integer, nullable=False) # e.g. 19900 = ₹199.00
    currency = Column(String(10), default='INR', nullable=False)
    billing_interval = Column(String(20), nullable=False) # monthly, quarterly, yearly, lifetime
    trial_days = Column(Integer, default=0, nullable=False)
    benefits = Column(JSON, default=list, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    available_from = Column(DateTime(timezone=True), nullable=True)
    available_until = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan = relationship('SubscriptionPlan', back_populates='versions')
    entitlements = relationship('PlanEntitlement', back_populates='plan_version', cascade='all, delete-orphan')


class PlanEntitlement(Base):
    __tablename__ = 'plan_entitlements'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_version_id = Column(String, ForeignKey('subscription_plan_versions.id', ondelete='CASCADE'), nullable=False, index=True)
    feature_key = Column(String(50), nullable=False) # kisan_chat, diagnose_leaf, mandi_price, etc.
    enabled = Column(Boolean, default=True, nullable=False)
    usage_limit = Column(Integer, nullable=True) # None = unlimited
    limit_period = Column(String(20), nullable=True) # daily, monthly, total
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan_version = relationship('SubscriptionPlanVersion', back_populates='entitlements')


class UserSubscription(Base):
    __tablename__ = 'user_subscriptions'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    plan_version_id = Column(String, ForeignKey('subscription_plan_versions.id'), nullable=False)
    status = Column(String(20), default='active', nullable=False) # trialing, active, past_due, canceled, expired
    current_period_start = Column(DateTime(timezone=True), server_default=func.now())
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship('User')
    plan_version = relationship('SubscriptionPlanVersion')


class SubscriptionUsage(Base):
    __tablename__ = 'subscription_usage'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    feature_key = Column(String(50), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    used = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PaymentOrder(Base):
    __tablename__ = 'payment_orders'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    plan_version_id = Column(String, ForeignKey('subscription_plan_versions.id'), nullable=False)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String(10), default='INR', nullable=False)
    status = Column(String(20), default='created', nullable=False) # created, attempted, paid, failed, refunded
    provider = Column(String(30), default='razorpay', nullable=False)
    provider_order_id = Column(String(100), unique=True, nullable=True)
    receipt = Column(String(100), nullable=True)
    notes = Column(JSON, default=dict, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PaymentTransaction(Base):
    __tablename__ = 'payment_transactions'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, ForeignKey('payment_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String(10), default='INR', nullable=False)
    status = Column(String(20), nullable=False) # success, failed, refunded, pending
    provider = Column(String(30), default='razorpay', nullable=False)
    provider_payment_id = Column(String(100), unique=True, nullable=True)
    provider_signature = Column(String(255), nullable=True)
    error_code = Column(String(50), nullable=True)
    error_description = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PaymentWebhookEvent(Base):
    __tablename__ = 'payment_webhook_events'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(30), default='razorpay', nullable=False)
    provider_event_id = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_log = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminAuditLog(Base):
    __tablename__ = 'admin_audit_logs'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    actor_role = Column(String(30), nullable=False)
    action = Column(String(100), nullable=False, index=True)
    target_entity = Column(String(100), nullable=False, index=True)
    target_id = Column(String(100), nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DataRequest(Base):
    __tablename__ = 'data_requests'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    request_type = Column(String(30), nullable=False)  # 'export', 'delete'
    status = Column(String(30), default='pending', nullable=False)  # 'pending', 'processing', 'completed', 'rejected'
    details = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    processed_by = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    admin_notes = Column(Text, nullable=True)


# ── BROADCAST POSTS & PROMOTIONAL OFFERS (APPROVAL ARCHITECTURE) ──

class BroadcastType(str, enum.Enum):
    post = 'post'
    offer = 'offer'
    advisory = 'advisory'


class BroadcastStatus(str, enum.Enum):
    draft = 'draft'
    pending_approval = 'pending_approval'
    approved = 'approved'
    rejected = 'rejected'
    archived = 'archived'


class BroadcastItem(Base):
    """Posts, updates, announcements, and promotional offers for farmers."""
    __tablename__ = 'broadcast_items'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    item_type = Column(Enum(BroadcastType), default=BroadcastType.post, nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    
    # Offer specific fields
    discount_percent = Column(Float, nullable=True)
    discount_code = Column(String(50), nullable=True)
    target_plan_slug = Column(String(50), nullable=True)
    banner_url = Column(String(500), nullable=True)
    tags = Column(JSON, default=list)
    
    # Status & Super Admin Approval
    status = Column(Enum(BroadcastStatus), default=BroadcastStatus.draft, nullable=False)
    
    created_by = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    
    approved_by = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    super_admin_notes = Column(Text, nullable=True)
    
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    author = relationship('User', foreign_keys=[created_by])
    approver = relationship('User', foreign_keys=[approved_by])


class GovernmentScheme(Base):
    """Real Central and State Government agricultural subsidy & support schemes."""
    __tablename__ = 'government_schemes'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    short_description = Column(Text, nullable=False)
    benefit_summary = Column(String(255), nullable=False)  # e.g. "₹6,000/yr Direct Cash Transfer"
    benefit_amount = Column(String(100), nullable=True)   # e.g. "₹6,000 / year"
    category = Column(String(100), nullable=False)        # Income Support, Crop Insurance, Irrigation, Credit, Mechanization, etc.
    level = Column(String(50), default="central")         # central, state
    state = Column(String(100), nullable=True)            # None for all-India central, or specific state
    
    # Eligibility constraints
    min_land_acres = Column(Float, nullable=True, default=0.0)
    max_land_acres = Column(Float, nullable=True)         # None = any size, or e.g. 5.0 for small/marginal
    eligible_crops = Column(JSON, default=list)           # [] = all crops
    eligible_farmer_types = Column(JSON, default=list)    # ["small", "marginal", "all"]
    eligible_states = Column(JSON, default=list)          # [] = all states
    
    # Details & Application
    application_portal = Column(String(500), nullable=False)
    application_process = Column(Text, nullable=True)
    required_documents = Column(JSON, default=list)
    key_highlights = Column(JSON, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ── AGRO AI MART: FARM-TO-CONSUMER FRESH PRODUCE MARKETPLACE ───

class MartCategory(Base):
    __tablename__ = 'mart_categories'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(50), unique=True, nullable=False, index=True) # vegetables, fruits, leafy-greens
    name_en = Column(String(100), nullable=False)
    name_hi = Column(String(100), nullable=False)
    name_kn = Column(String(100), nullable=False)
    icon = Column(String(20), default='🥬', nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class MartCatalogItem(Base):
    """Admin-curated reference produce item types (e.g. Tomato, Onion, Spinach)."""
    __tablename__ = 'mart_catalog_items'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id = Column(String, ForeignKey('mart_categories.id', ondelete='CASCADE'), nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name_en = Column(String(100), nullable=False)
    name_hi = Column(String(100), nullable=False)
    name_kn = Column(String(100), nullable=False)
    allowed_units = Column(JSON, default=lambda: ['kg', '500g', 'bunch', 'piece', 'dozen'], nullable=False)
    image_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    category = relationship('MartCategory')


class MartServiceRegion(Base):
    """Regions (State/District) opened by Head Super Admin for Mart operations."""
    __tablename__ = 'mart_service_regions'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    state = Column(String(100), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)
    pincodes = Column(JSON, default=list, nullable=False) # list of active PIN codes
    is_enabled = Column(Boolean, default=True, nullable=False)
    opened_by = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    opened_at = Column(DateTime(timezone=True), server_default=func.now())


class MartSellerProfile(Base):
    """Verified farmer seller profile applying to sell produce on Agro AI Mart."""
    __tablename__ = 'mart_seller_profiles'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), unique=True, index=True, nullable=False)
    farm_name = Column(String(150), nullable=False)
    contact_phone = Column(String(20), nullable=False)
    state = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    village = Column(String(150), nullable=False)
    service_pincodes = Column(JSON, default=list, nullable=False) # PIN codes the farmer can deliver to or allow pickup from
    fulfilment_modes = Column(JSON, default=lambda: ['pickup', 'delivery'], nullable=False)
    
    # State machine: DRAFT, SUBMITTED, UNDER_REVIEW, INFO_REQUIRED, APPROVED, REJECTED, SUSPENDED
    status = Column(String(30), default='DRAFT', nullable=False, index=True)
    
    # Verification Checklist
    proof_type = Column(String(100), nullable=True) # e.g. 'Pahani / RTC (Karnataka)', '7/12 Extract', 'FPO Letter'
    proof_document_url = Column(String(500), nullable=True)
    phone_verified = Column(Boolean, default=True, nullable=False)
    staff_call_completed = Column(Boolean, default=False, nullable=False)
    declaration_cultivates_produce = Column(Boolean, default=False, nullable=False)
    review_notes = Column(Text, nullable=True)
    reviewed_by = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship('User', foreign_keys=[user_id])
    reviewer = relationship('User', foreign_keys=[reviewed_by])


class MartListing(Base):
    """Farmer product listing for fresh produce."""
    __tablename__ = 'mart_listings'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    seller_id = Column(String, ForeignKey('mart_seller_profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    catalog_item_id = Column(String, ForeignKey('mart_catalog_items.id'), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    price_minor = Column(Integer, nullable=False) # Price in paise (e.g. 4000 = ₹40.00)
    currency = Column(String(10), default='INR', nullable=False)
    unit = Column(String(20), default='kg', nullable=False) # kg, 500g, bunch, piece, dozen
    min_order_qty = Column(Float, default=1.0, nullable=False)
    stock_quantity = Column(Float, default=0.0, nullable=False)
    harvest_date = Column(String(50), nullable=False) # e.g. '2026-10-14'
    available_from = Column(DateTime(timezone=True), server_default=func.now())
    fulfilment_type = Column(String(30), default='BOTH', nullable=False) # PICKUP, DELIVERY, BOTH
    
    # State machine: DRAFT, SUBMITTED, UNDER_REVIEW, INFO_REQUIRED, APPROVED, REJECTED, PAUSED, SUSPENDED, ARCHIVED
    status = Column(String(30), default='DRAFT', nullable=False, index=True)
    rejection_reason = Column(Text, nullable=True)
    
    is_organic_claim = Column(Boolean, default=False, nullable=False)
    claim_reviewed = Column(Boolean, default=False, nullable=False)
    photos = Column(JSON, default=list, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    seller = relationship('MartSellerProfile')
    catalog_item = relationship('MartCatalogItem')


class MartOrder(Base):
    """Direct consumer-to-farmer order (one farm per order)."""
    __tablename__ = 'mart_orders'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_id = Column(String, ForeignKey('mart_seller_profiles.id'), nullable=False, index=True)
    
    # State machine: PLACED, ACCEPTED_BY_SELLER, PREPARING, READY_FOR_PICKUP, OUT_FOR_DELIVERY, COMPLETED, CANCELLED, REJECTED, DISPUTED
    status = Column(String(30), default='PLACED', nullable=False, index=True)
    fulfilment_type = Column(String(30), default='DELIVERY', nullable=False) # DELIVERY or PICKUP
    delivery_address = Column(JSON, nullable=False)
    delivery_pincode = Column(String(10), nullable=False, index=True)
    
    subtotal_minor = Column(Integer, nullable=False)
    delivery_fee_minor = Column(Integer, default=0, nullable=False)
    total_minor = Column(Integer, nullable=False)
    currency = Column(String(10), default='INR', nullable=False)
    
    # Pilot payment rules: Pay directly to farmer (Cash / UPI)
    payment_method = Column(String(50), default='PAY_ON_DELIVERY', nullable=False)
    payment_status = Column(String(50), default='NOT_COLLECTED_BY_PLATFORM', nullable=False)
    seller_payment_confirmed = Column(Boolean, default=False, nullable=False)
    
    cancellation_reason = Column(Text, nullable=True)
    dispute_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    customer = relationship('User')
    seller = relationship('MartSellerProfile')
    items = relationship('MartOrderItem', back_populates='order', cascade='all, delete-orphan')


class MartOrderItem(Base):
    __tablename__ = 'mart_order_items'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, ForeignKey('mart_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    listing_id = Column(String, ForeignKey('mart_listings.id'), nullable=False)
    item_title = Column(String(150), nullable=False)
    unit = Column(String(20), nullable=False)
    unit_price_minor = Column(Integer, nullable=False)
    quantity = Column(Float, nullable=False)
    total_minor = Column(Integer, nullable=False)

    order = relationship('MartOrder', back_populates='items')
    listing = relationship('MartListing')


class MartOrderStatusHistory(Base):
    __tablename__ = 'mart_order_status_history'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, ForeignKey('mart_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=False)
    actor_id = Column(String, nullable=True)
    actor_role = Column(String(50), nullable=True) # customer, seller, admin
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MartWaitlist(Base):
    """Waitlist of customers requesting farm-to-consumer delivery in unserved PIN codes."""
    __tablename__ = 'mart_waitlist'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    phone = Column(String(20), nullable=True)
    pincode = Column(String(10), nullable=False, index=True)
    district = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MartHarvestOffer(Base):
    """Agro AI Harvest Circle: Upcoming harvest lot offered by verified farmers."""
    __tablename__ = 'mart_harvest_offers'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    seller_id = Column(String, ForeignKey('mart_seller_profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    catalog_item_id = Column(String, ForeignKey('mart_catalog_items.id'), nullable=False)
    crop_name = Column(String(150), nullable=False)
    estimated_quantity = Column(Float, nullable=False)
    unit = Column(String(20), default='kg')
    target_harvest_start = Column(String(20), nullable=False) # YYYY-MM-DD
    target_harvest_end = Column(String(20), nullable=False)
    proposed_price_minor = Column(Integer, nullable=False)
    min_demand_threshold = Column(Float, default=10.0) # minimum aggregated kg to commit
    service_pincodes = Column(JSON, default=list) # e.g. ["560034", "571401"]
    status = Column(String(30), default='PROPOSED') # PROPOSED, THRESHOLD_REACHED, CONFIRMED, CANCELLED
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    seller = relationship('MartSellerProfile')
    catalog_item = relationship('MartCatalogItem')
    demands = relationship('MartHarvestDemand', back_populates='offer', cascade='all, delete-orphan')


class MartHarvestDemand(Base):
    """Customer expressed interest in an upcoming harvest lot."""
    __tablename__ = 'mart_harvest_demands'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    offer_id = Column(String, ForeignKey('mart_harvest_offers.id', ondelete='CASCADE'), nullable=False, index=True)
    customer_id = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    pincode = Column(String(10), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    contact_phone = Column(String(20), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    offer = relationship('MartHarvestOffer', back_populates='demands')



