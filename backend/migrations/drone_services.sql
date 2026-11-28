-- Drone Services: approval-gated provider discovery and bookings.
-- Additive migration. Existing drone_operators records are intentionally retained
-- but are no longer used by the farmer-facing API.

CREATE TABLE IF NOT EXISTS drone_companies (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    registered_name VARCHAR(180) NOT NULL,
    brand_name VARCHAR(120),
    representative_name VARCHAR(120) NOT NULL,
    contact_email VARCHAR(255),
    state VARCHAR(80) NOT NULL,
    district VARCHAR(100) NOT NULL,
    address TEXT,
    business_registration VARCHAR(120),
    service_categories JSON NOT NULL DEFAULT '[]',
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    CONSTRAINT ck_drone_companies_status CHECK (status IN ('pending','under_review','more_information_required','approved','rejected','suspended','expired'))
);
CREATE INDEX IF NOT EXISTS ix_drone_companies_status_active ON drone_companies(status, is_active);
CREATE INDEX IF NOT EXISTS ix_drone_companies_location ON drone_companies(state, district);
CREATE INDEX IF NOT EXISTS ix_drone_companies_owner_user_id ON drone_companies(owner_user_id);

CREATE TABLE IF NOT EXISTS drone_pilots (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    company_id TEXT REFERENCES drone_companies(id) ON DELETE SET NULL,
    full_name VARCHAR(150) NOT NULL,
    photo_url VARCHAR(500),
    state VARCHAR(80) NOT NULL,
    district VARCHAR(100) NOT NULL,
    taluk VARCHAR(100),
    village VARCHAR(120),
    qualification VARCHAR(180),
    certificate_number VARCHAR(120),
    certificate_issuer VARCHAR(180),
    certificate_expiry DATE,
    credentials_verified BOOLEAN NOT NULL DEFAULT FALSE,
    years_experience INTEGER NOT NULL DEFAULT 0 CHECK (years_experience >= 0),
    languages JSON NOT NULL DEFAULT '[]',
    services JSON NOT NULL DEFAULT '[]',
    availability JSON NOT NULL DEFAULT '{}',
    price_per_acre NUMERIC(10,2) CHECK (price_per_acre IS NULL OR price_per_acre >= 0),
    price_per_hour NUMERIC(10,2),
    minimum_booking_amount NUMERIC(10,2),
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    CONSTRAINT ck_drone_pilots_status CHECK (status IN ('pending','under_review','more_information_required','approved','rejected','suspended','expired'))
);
CREATE INDEX IF NOT EXISTS ix_drone_pilots_status_active ON drone_pilots(status, is_active);
CREATE INDEX IF NOT EXISTS ix_drone_pilots_location ON drone_pilots(state, district, taluk);
CREATE INDEX IF NOT EXISTS ix_drone_pilots_company_owner ON drone_pilots(company_id, owner_user_id);
CREATE INDEX IF NOT EXISTS ix_drone_pilots_owner_user_id ON drone_pilots(owner_user_id);

CREATE TABLE IF NOT EXISTS drone_fleet (
    id TEXT PRIMARY KEY,
    pilot_id TEXT NOT NULL REFERENCES drone_pilots(id) ON DELETE CASCADE,
    manufacturer VARCHAR(120),
    model VARCHAR(150) NOT NULL,
    serial_number VARCHAR(120) UNIQUE,
    registration_number VARCHAR(120),
    capabilities JSON NOT NULL DEFAULT '[]',
    payload_litres NUMERIC(8,2),
    equipment_details TEXT,
    inspection_due DATE,
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_drone_fleet_status CHECK (status IN ('pending','active','maintenance','suspended','expired'))
);
CREATE INDEX IF NOT EXISTS ix_drone_fleet_pilot_id ON drone_fleet(pilot_id);
CREATE INDEX IF NOT EXISTS ix_drone_fleet_suitability ON drone_fleet(pilot_id, status);

CREATE TABLE IF NOT EXISTS drone_service_areas (
    id TEXT PRIMARY KEY,
    pilot_id TEXT NOT NULL REFERENCES drone_pilots(id) ON DELETE CASCADE,
    state VARCHAR(80) NOT NULL,
    district VARCHAR(100) NOT NULL,
    taluk VARCHAR(100),
    village VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_drone_service_area UNIQUE(pilot_id, state, district, taluk, village)
);
CREATE INDEX IF NOT EXISTS ix_drone_service_areas_search ON drone_service_areas(state, district, taluk);
CREATE INDEX IF NOT EXISTS ix_drone_service_areas_pilot_id ON drone_service_areas(pilot_id);

CREATE TABLE IF NOT EXISTS drone_applications (
    id TEXT PRIMARY KEY,
    applicant_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    application_type VARCHAR(24) NOT NULL CHECK (application_type IN ('individual','company','copilot')),
    data JSON NOT NULL DEFAULT '{}',
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    review_notes TEXT,
    created_by_admin TEXT REFERENCES users(id) ON DELETE SET NULL,
    result_pilot_id TEXT REFERENCES drone_pilots(id) ON DELETE SET NULL,
    result_company_id TEXT REFERENCES drone_companies(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_drone_applications_status CHECK (status IN ('draft','pending','under_review','more_information_required','approved','rejected','suspended','expired','on_hold'))
);
CREATE INDEX IF NOT EXISTS ix_drone_applications_review_queue ON drone_applications(status, submitted_at);
CREATE INDEX IF NOT EXISTS ix_drone_applications_owner ON drone_applications(applicant_user_id, submitted_at);

CREATE TABLE IF NOT EXISTS drone_pilot_documents (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES drone_applications(id) ON DELETE CASCADE,
    uploaded_by TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    document_type VARCHAR(64) NOT NULL,
    object_key VARCHAR(500) NOT NULL UNIQUE,
    original_filename VARCHAR(180) NOT NULL,
    content_type VARCHAR(80) NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 10485760),
    verification_status VARCHAR(24) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_drone_pilot_documents_application_id ON drone_pilot_documents(application_id);

CREATE TABLE IF NOT EXISTS drone_approval_history (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES drone_applications(id) ON DELETE CASCADE,
    actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(40) NOT NULL,
    previous_status VARCHAR(40),
    new_status VARCHAR(40) NOT NULL,
    reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_drone_approval_history_application_id ON drone_approval_history(application_id);

CREATE TABLE IF NOT EXISTS drone_bookings (
    id TEXT PRIMARY KEY,
    farmer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    provider_pilot_id TEXT NOT NULL REFERENCES drone_pilots(id) ON DELETE RESTRICT,
    assigned_drone_id TEXT REFERENCES drone_fleet(id) ON DELETE RESTRICT,
    service_category VARCHAR(48) NOT NULL,
    farm_state VARCHAR(80) NOT NULL,
    farm_district VARCHAR(100) NOT NULL,
    farm_taluk VARCHAR(100),
    farm_village VARCHAR(120),
    area_acres NUMERIC(10,2) NOT NULL CHECK (area_acres > 0),
    scheduled_date DATE NOT NULL,
    quoted_total NUMERIC(12,2) NOT NULL CHECK (quoted_total >= 0),
    price_snapshot JSON NOT NULL DEFAULT '{}',
    status VARCHAR(32) NOT NULL DEFAULT 'requested',
    farmer_notes TEXT,
    provider_notes TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT ck_drone_bookings_status CHECK (status IN ('requested','accepted','rejected','pilot_assigned','scheduled','on_the_way','in_progress','awaiting_farmer_confirmation','completed','cancelled','disputed'))
);
CREATE INDEX IF NOT EXISTS ix_drone_bookings_farmer_created ON drone_bookings(farmer_user_id, requested_at);
CREATE INDEX IF NOT EXISTS ix_drone_bookings_pilot_status_date ON drone_bookings(provider_pilot_id, status, scheduled_date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_drone_booking_pilot_day
    ON drone_bookings(provider_pilot_id, scheduled_date)
    WHERE status IN ('accepted','pilot_assigned','scheduled','on_the_way','in_progress');
CREATE UNIQUE INDEX IF NOT EXISTS uq_drone_booking_drone_day
    ON drone_bookings(assigned_drone_id, scheduled_date)
    WHERE assigned_drone_id IS NOT NULL AND status IN ('accepted','pilot_assigned','scheduled','on_the_way','in_progress');

CREATE TABLE IF NOT EXISTS drone_booking_status_history (
    id TEXT PRIMARY KEY,
    booking_id TEXT NOT NULL REFERENCES drone_bookings(id) ON DELETE CASCADE,
    actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    previous_status VARCHAR(32),
    new_status VARCHAR(32) NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_drone_booking_status_history_booking_id ON drone_booking_status_history(booking_id);

CREATE TABLE IF NOT EXISTS drone_role_assignments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    company_id TEXT REFERENCES drone_companies(id) ON DELETE SET NULL,
    role VARCHAR(32) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    requested_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    approved_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_drone_role_assignments_role CHECK (role IN ('copilot','company_manager','company_operator')),
    CONSTRAINT ck_drone_role_assignments_status CHECK (status IN ('pending','awaiting_person_confirmation','approved','rejected','revoked'))
);
CREATE INDEX IF NOT EXISTS ix_drone_role_assignments_user_status ON drone_role_assignments(user_id, status);
CREATE INDEX IF NOT EXISTS ix_drone_role_assignments_company_id ON drone_role_assignments(company_id);

CREATE TABLE IF NOT EXISTS drone_reviews (
    id TEXT PRIMARY KEY,
    booking_id TEXT NOT NULL UNIQUE REFERENCES drone_bookings(id) ON DELETE RESTRICT,
    farmer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    pilot_id TEXT NOT NULL REFERENCES drone_pilots(id) ON DELETE RESTRICT,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_drone_reviews_pilot_id ON drone_reviews(pilot_id);

-- All authorization is enforced in FastAPI. RLS provides a default-deny
-- backstop if this database is also exposed through Supabase's Data API.
ALTER TABLE drone_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE drone_pilots ENABLE ROW LEVEL SECURITY;
ALTER TABLE drone_fleet ENABLE ROW LEVEL SECURITY;
ALTER TABLE drone_service_areas ENABLE ROW LEVEL SECURITY;
ALTER TABLE drone_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE drone_pilot_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE drone_approval_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE drone_bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE drone_booking_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE drone_role_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE drone_reviews ENABLE ROW LEVEL SECURITY;
