-- ============================================================
-- AGRO AI — SUPABASE POSTGRESQL SCHEMA MIGRATION
-- Project Ref: eziigoiirqdsgimfkquv
-- Run this directly in the Supabase SQL Editor or via migrate_to_supabase.py
-- ============================================================

-- 1. Enum Types
DO $$ BEGIN
    CREATE TYPE userrole AS ENUM ('farmer', 'driver', 'expert', 'admin');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
DO $$ BEGIN
    CREATE TYPE adminuserrole AS ENUM ('super_admin', 'listing_reviewer', 'seller_reviewer', 'plan_manager', 'payment_manager', 'payment_staff', 'support_agent', 'content_manager', 'analyst');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
DO $$ BEGIN
    CREATE TYPE broadcasttype AS ENUM ('post', 'offer', 'advisory');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
DO $$ BEGIN
    CREATE TYPE broadcaststatus AS ENUM ('draft', 'pending_approval', 'approved', 'rejected', 'archived');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
DO $$ BEGIN
    CREATE TYPE verificationstatus AS ENUM ('pending', 'verified', 'rejected', 'suspended', 'expired');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
DO $$ BEGIN
    CREATE TYPE tripstatus AS ENUM ('REQUESTED', 'MATCHING', 'DRIVER_ASSIGNED', 'DRIVER_EN_ROUTE', 'ARRIVED', 'LOADING', 'IN_TRANSIT', 'ARRIVED_DESTINATION', 'UNLOADING', 'COMPLETED', 'CANCELLED', 'DISPUTED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 2. Tables
CREATE TABLE IF NOT EXISTS ai_usage (
	id VARCHAR NOT NULL, 
	farmer_id VARCHAR, 
	provider VARCHAR(50), 
	model VARCHAR(100), 
	prompt_tokens INTEGER, 
	completion_tokens INTEGER, 
	latency_ms FLOAT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS api_logs (
	id VARCHAR NOT NULL, 
	request_id VARCHAR(100), 
	user_id VARCHAR, 
	endpoint VARCHAR(200), 
	provider VARCHAR(50), 
	model VARCHAR(100), 
	latency_ms FLOAT, 
	status_code INTEGER, 
	error_code VARCHAR(50), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS drone_operators (
	id VARCHAR NOT NULL, 
	name VARCHAR(150), 
	company VARCHAR(150), 
	dgca_registration VARCHAR(100), 
	is_verified BOOLEAN, 
	lat FLOAT, 
	lon FLOAT, 
	drone_model VARCHAR(100), 
	rate_per_acre FLOAT, 
	min_booking_charge FLOAT, 
	travel_charge_per_km FLOAT, 
	available_today BOOLEAN, 
	contact_phone VARCHAR(15), 
	rating FLOAT, 
	last_updated TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS government_schemes (
	id VARCHAR NOT NULL, 
	slug VARCHAR(100) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	short_description TEXT NOT NULL, 
	benefit_summary VARCHAR(255) NOT NULL, 
	benefit_amount VARCHAR(100), 
	category VARCHAR(100) NOT NULL, 
	level VARCHAR(50), 
	state VARCHAR(100), 
	min_land_acres FLOAT, 
	max_land_acres FLOAT, 
	eligible_crops JSON, 
	eligible_farmer_types JSON, 
	eligible_states JSON, 
	application_portal VARCHAR(500) NOT NULL, 
	application_process TEXT, 
	required_documents JSON, 
	key_highlights JSON, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS market_prices (
	id VARCHAR NOT NULL, 
	commodity VARCHAR(100), 
	variety VARCHAR(100), 
	market_name VARCHAR(150), 
	state VARCHAR(100), 
	district VARCHAR(100), 
	min_price FLOAT, 
	max_price FLOAT, 
	modal_price FLOAT, 
	unit VARCHAR(20), 
	price_date TIMESTAMP WITH TIME ZONE, 
	data_source VARCHAR(100), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS marketplace_sellers (
	id VARCHAR NOT NULL, 
	name VARCHAR(150), 
	seller_type VARCHAR(50), 
	license_number VARCHAR(100), 
	district VARCHAR(100), 
	state VARCHAR(100), 
	lat FLOAT, 
	lon FLOAT, 
	rating FLOAT, 
	is_verified BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS mart_categories (
	id VARCHAR NOT NULL, 
	slug VARCHAR(50) NOT NULL, 
	name_en VARCHAR(100) NOT NULL, 
	name_hi VARCHAR(100) NOT NULL, 
	name_kn VARCHAR(100) NOT NULL, 
	icon VARCHAR(20) NOT NULL, 
	sort_order INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS payment_webhook_events (
	id VARCHAR NOT NULL, 
	provider VARCHAR(30) NOT NULL, 
	provider_event_id VARCHAR(100) NOT NULL, 
	event_type VARCHAR(100) NOT NULL, 
	payload JSON NOT NULL, 
	processed BOOLEAN NOT NULL, 
	processed_at TIMESTAMP WITH TIME ZONE, 
	error_log TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS platform_feature_history (
	id VARCHAR NOT NULL, 
	feature_key VARCHAR(50) NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	config JSON NOT NULL, 
	revision INTEGER NOT NULL, 
	changed_by VARCHAR, 
	changed_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	reason TEXT, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS subscription_plans (
	id VARCHAR NOT NULL, 
	slug VARCHAR(50) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS users (
	id VARCHAR NOT NULL, 
	phone VARCHAR(15), 
	email VARCHAR(255), 
	password_hash VARCHAR(255), 
	full_name VARCHAR(100), 
	role userrole, 
	preferred_language VARCHAR(10), 
	is_verified BOOLEAN, 
	is_active BOOLEAN, 
	is_test BOOLEAN NOT NULL, 
	avatar_url VARCHAR(500), 
	fcm_token VARCHAR(500), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS weather_cache (
	id VARCHAR NOT NULL, 
	pincode VARCHAR(10), 
	lat FLOAT, 
	lon FLOAT, 
	data JSON, 
	data_source VARCHAR(100), 
	fetched_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	expires_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS admin_access_requests (
	id VARCHAR NOT NULL, 
	user_id VARCHAR, 
	email VARCHAR(255) NOT NULL, 
	full_name VARCHAR(100) NOT NULL, 
	requested_role VARCHAR(50) NOT NULL, 
	notes TEXT, 
	status VARCHAR(20) NOT NULL, 
	reviewed_by VARCHAR, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS admin_audit_logs (
	id VARCHAR NOT NULL, 
	actor_id VARCHAR, 
	actor_role VARCHAR(30) NOT NULL, 
	action VARCHAR(100) NOT NULL, 
	target_entity VARCHAR(100) NOT NULL, 
	target_id VARCHAR(100), 
	details JSON, 
	ip_address VARCHAR(50), 
	user_agent VARCHAR(255), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS admin_users (
	id VARCHAR NOT NULL, 
	user_id VARCHAR, 
	role adminuserrole NOT NULL, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agro_gpt_conversations (
	id VARCHAR NOT NULL, 
	farmer_id VARCHAR, 
	title VARCHAR(200), 
	language VARCHAR(10), 
	context_data JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(farmer_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_context (
	id VARCHAR NOT NULL, 
	farmer_id VARCHAR, 
	active_diagnosis_id VARCHAR, 
	last_known_lat FLOAT, 
	last_known_lon FLOAT, 
	context_json JSON, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(farmer_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS broadcast_items (
	id VARCHAR NOT NULL, 
	item_type broadcasttype NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	content TEXT NOT NULL, 
	discount_percent FLOAT, 
	discount_code VARCHAR(50), 
	target_plan_slug VARCHAR(50), 
	banner_url VARCHAR(500), 
	tags JSON, 
	status broadcaststatus NOT NULL, 
	created_by VARCHAR, 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	approved_by VARCHAR, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	super_admin_notes TEXT, 
	valid_from TIMESTAMP WITH TIME ZONE, 
	valid_until TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS carbon_credits (
	id VARCHAR NOT NULL, 
	user_id VARCHAR, 
	tonnes_offset FLOAT, 
	status VARCHAR(50), 
	blockchain_hash VARCHAR(200), 
	payout_amount FLOAT, 
	payout_upi VARCHAR(100), 
	verification_agency VARCHAR(100), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	verified_at TIMESTAMP WITH TIME ZONE, 
	paid_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS data_requests (
	id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	request_type VARCHAR(30) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	details JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	processed_by VARCHAR, 
	processed_at TIMESTAMP WITH TIME ZONE, 
	admin_notes TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(processed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS drivers (
	id VARCHAR NOT NULL, 
	user_id VARCHAR, 
	driving_licence_number VARCHAR(50), 
	verification_status verificationstatus, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	document_expiry TIMESTAMP WITH TIME ZONE, 
	verification_provider VARCHAR(100), 
	verification_reference VARCHAR(100), 
	bank_upi_id VARCHAR(100), 
	emergency_contact VARCHAR(15), 
	is_online BOOLEAN, 
	is_busy BOOLEAN, 
	current_lat FLOAT, 
	current_lon FLOAT, 
	last_heartbeat TIMESTAMP WITH TIME ZONE, 
	rating FLOAT, 
	total_trips INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS farms (
	id VARCHAR NOT NULL, 
	user_id VARCHAR, 
	village VARCHAR(100), 
	district VARCHAR(100), 
	state VARCHAR(100), 
	pincode VARCHAR(10), 
	latitude FLOAT, 
	longitude FLOAT, 
	total_acres FLOAT, 
	owned_acres FLOAT, 
	leased_acres FLOAT, 
	gps_boundary JSON, 
	irrigation_method VARCHAR(50), 
	soil_type VARCHAR(50), 
	water_source VARCHAR(50), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS marketplace_products (
	id VARCHAR NOT NULL, 
	seller_id VARCHAR, 
	title VARCHAR(200), 
	category VARCHAR(50), 
	brand VARCHAR(100), 
	pack_size VARCHAR(50), 
	pack_size_value FLOAT, 
	mrp FLOAT, 
	current_price FLOAT, 
	in_stock BOOLEAN, 
	stock_count INTEGER, 
	delivery_charge FLOAT, 
	delivery_estimate_days INTEGER, 
	data_source VARCHAR(100), 
	last_updated TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(seller_id) REFERENCES marketplace_sellers (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mart_catalog_items (
	id VARCHAR NOT NULL, 
	category_id VARCHAR NOT NULL, 
	slug VARCHAR(100) NOT NULL, 
	name_en VARCHAR(100) NOT NULL, 
	name_hi VARCHAR(100) NOT NULL, 
	name_kn VARCHAR(100) NOT NULL, 
	allowed_units JSON NOT NULL, 
	image_url VARCHAR(500), 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES mart_categories (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mart_seller_profiles (
	id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	farm_name VARCHAR(150) NOT NULL, 
	contact_phone VARCHAR(20) NOT NULL, 
	state VARCHAR(100) NOT NULL, 
	district VARCHAR(100) NOT NULL, 
	village VARCHAR(150) NOT NULL, 
	service_pincodes JSON NOT NULL, 
	fulfilment_modes JSON NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	proof_type VARCHAR(100), 
	proof_document_url VARCHAR(500), 
	phone_verified BOOLEAN NOT NULL, 
	staff_call_completed BOOLEAN NOT NULL, 
	declaration_cultivates_produce BOOLEAN NOT NULL, 
	review_notes TEXT, 
	reviewed_by VARCHAR, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mart_service_regions (
	id VARCHAR NOT NULL, 
	state VARCHAR(100) NOT NULL, 
	district VARCHAR(100) NOT NULL, 
	pincodes JSON NOT NULL, 
	is_enabled BOOLEAN NOT NULL, 
	opened_by VARCHAR, 
	opened_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(opened_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mart_waitlist (
	id VARCHAR NOT NULL, 
	user_id VARCHAR, 
	phone VARCHAR(20), 
	pincode VARCHAR(10) NOT NULL, 
	district VARCHAR(100), 
	state VARCHAR(100), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS platform_features (
	key VARCHAR(50) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	implemented BOOLEAN NOT NULL, 
	config JSON NOT NULL, 
	revision INTEGER NOT NULL, 
	changed_by VARCHAR, 
	changed_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	reason TEXT, 
	PRIMARY KEY (key), 
	FOREIGN KEY(changed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS subscription_plan_versions (
	id VARCHAR NOT NULL, 
	plan_id VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	price_minor INTEGER NOT NULL, 
	currency VARCHAR(10) NOT NULL, 
	billing_interval VARCHAR(20) NOT NULL, 
	trial_days INTEGER NOT NULL, 
	benefits JSON NOT NULL, 
	is_published BOOLEAN NOT NULL, 
	available_from TIMESTAMP WITH TIME ZONE, 
	available_until TIMESTAMP WITH TIME ZONE, 
	created_by VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(plan_id) REFERENCES subscription_plans (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subscription_usage (
	id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	feature_key VARCHAR(50) NOT NULL, 
	period_start TIMESTAMP WITH TIME ZONE NOT NULL, 
	used INTEGER NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_sessions (
	id VARCHAR NOT NULL, 
	user_id VARCHAR, 
	refresh_token VARCHAR(500), 
	device_info VARCHAR(255), 
	ip_address VARCHAR(50), 
	is_active BOOLEAN, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agro_gpt_messages (
	id VARCHAR NOT NULL, 
	conversation_id VARCHAR, 
	role VARCHAR(20), 
	content TEXT, 
	language VARCHAR(10), 
	context_references JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES agro_gpt_conversations (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS driver_documents (
	id VARCHAR NOT NULL, 
	driver_id VARCHAR, 
	doc_type VARCHAR(50), 
	doc_number VARCHAR(100), 
	file_path VARCHAR(500), 
	file_url VARCHAR(500), 
	issued_at TIMESTAMP WITH TIME ZONE, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	verification_status verificationstatus, 
	rejection_reason VARCHAR(255), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(driver_id) REFERENCES drivers (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS farm_crops (
	id VARCHAR NOT NULL, 
	farm_id VARCHAR, 
	crop_name VARCHAR(100), 
	crop_variety VARCHAR(100), 
	season VARCHAR(50), 
	sown_date TIMESTAMP WITH TIME ZONE, 
	expected_harvest_date TIMESTAMP WITH TIME ZONE, 
	area_acres FLOAT, 
	expected_yield FLOAT, 
	actual_yield FLOAT, 
	input_cost FLOAT, 
	selling_price FLOAT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(farm_id) REFERENCES farms (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fields (
	id VARCHAR NOT NULL, 
	farm_id VARCHAR, 
	name VARCHAR(100), 
	area_acres FLOAT, 
	current_crop VARCHAR(100), 
	soil_type VARCHAR(50), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(farm_id) REFERENCES farms (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mart_bulk_buying_groups (
	id VARCHAR NOT NULL, 
	seller_id VARCHAR NOT NULL, 
	catalog_item_id VARCHAR NOT NULL, 
	title VARCHAR(150) NOT NULL, 
	target_pincode VARCHAR(10) NOT NULL, 
	min_threshold_qty FLOAT NOT NULL, 
	current_committed_qty FLOAT NOT NULL, 
	unit VARCHAR(20), 
	regular_price_minor INTEGER NOT NULL, 
	group_price_minor INTEGER NOT NULL, 
	status VARCHAR(30), 
	expires_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(seller_id) REFERENCES mart_seller_profiles (id) ON DELETE CASCADE, 
	FOREIGN KEY(catalog_item_id) REFERENCES mart_catalog_items (id)
);

CREATE TABLE IF NOT EXISTS mart_harvest_offers (
	id VARCHAR NOT NULL, 
	seller_id VARCHAR NOT NULL, 
	catalog_item_id VARCHAR NOT NULL, 
	crop_name VARCHAR(150) NOT NULL, 
	estimated_quantity FLOAT NOT NULL, 
	unit VARCHAR(20), 
	target_harvest_start VARCHAR(20) NOT NULL, 
	target_harvest_end VARCHAR(20) NOT NULL, 
	proposed_price_minor INTEGER NOT NULL, 
	min_demand_threshold FLOAT, 
	service_pincodes JSON, 
	status VARCHAR(30), 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(seller_id) REFERENCES mart_seller_profiles (id) ON DELETE CASCADE, 
	FOREIGN KEY(catalog_item_id) REFERENCES mart_catalog_items (id)
);

CREATE TABLE IF NOT EXISTS mart_listings (
	id VARCHAR NOT NULL, 
	seller_id VARCHAR NOT NULL, 
	catalog_item_id VARCHAR NOT NULL, 
	title VARCHAR(150) NOT NULL, 
	description TEXT, 
	price_minor INTEGER NOT NULL, 
	currency VARCHAR(10) NOT NULL, 
	unit VARCHAR(20) NOT NULL, 
	min_order_qty FLOAT NOT NULL, 
	stock_quantity FLOAT NOT NULL, 
	harvest_date VARCHAR(50) NOT NULL, 
	available_from TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	fulfilment_type VARCHAR(30) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	rejection_reason TEXT, 
	is_organic_claim BOOLEAN NOT NULL, 
	claim_reviewed BOOLEAN NOT NULL, 
	photos JSON NOT NULL, 
	batch_number VARCHAR(50), 
	is_surplus BOOLEAN NOT NULL, 
	surplus_discount_percent FLOAT NOT NULL, 
	surplus_valid_until TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(seller_id) REFERENCES mart_seller_profiles (id) ON DELETE CASCADE, 
	FOREIGN KEY(catalog_item_id) REFERENCES mart_catalog_items (id)
);

CREATE TABLE IF NOT EXISTS mart_orders (
	id VARCHAR NOT NULL, 
	order_number VARCHAR(50) NOT NULL, 
	customer_id VARCHAR NOT NULL, 
	seller_id VARCHAR NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	fulfilment_type VARCHAR(30) NOT NULL, 
	delivery_address JSON NOT NULL, 
	delivery_pincode VARCHAR(10) NOT NULL, 
	subtotal_minor INTEGER NOT NULL, 
	delivery_fee_minor INTEGER NOT NULL, 
	total_minor INTEGER NOT NULL, 
	currency VARCHAR(10) NOT NULL, 
	payment_method VARCHAR(50) NOT NULL, 
	payment_status VARCHAR(50) NOT NULL, 
	seller_payment_confirmed BOOLEAN NOT NULL, 
	cancellation_reason TEXT, 
	dispute_notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(seller_id) REFERENCES mart_seller_profiles (id)
);

CREATE TABLE IF NOT EXISTS payment_orders (
	id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	plan_version_id VARCHAR NOT NULL, 
	amount_minor INTEGER NOT NULL, 
	currency VARCHAR(10) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	provider VARCHAR(30) NOT NULL, 
	provider_order_id VARCHAR(100), 
	receipt VARCHAR(100), 
	notes JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(plan_version_id) REFERENCES subscription_plan_versions (id), 
	UNIQUE (provider_order_id)
);

CREATE TABLE IF NOT EXISTS plan_entitlements (
	id VARCHAR NOT NULL, 
	plan_version_id VARCHAR NOT NULL, 
	feature_key VARCHAR(50) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	usage_limit INTEGER, 
	limit_period VARCHAR(20), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(plan_version_id) REFERENCES subscription_plan_versions (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_subscriptions (
	id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	plan_version_id VARCHAR NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	current_period_start TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	current_period_end TIMESTAMP WITH TIME ZONE NOT NULL, 
	cancel_at_period_end BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(plan_version_id) REFERENCES subscription_plan_versions (id)
);

CREATE TABLE IF NOT EXISTS vehicles (
	id VARCHAR NOT NULL, 
	driver_id VARCHAR, 
	vehicle_type VARCHAR(50), 
	registration_number VARCHAR(30), 
	payload_capacity_tons FLOAT, 
	fuel_type VARCHAR(20), 
	fuel_efficiency_kmpl FLOAT, 
	insurance_status verificationstatus, 
	fitness_status verificationstatus, 
	permit_status verificationstatus, 
	rate_per_km FLOAT, 
	base_charge FLOAT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(driver_id) REFERENCES drivers (id) ON DELETE CASCADE, 
	UNIQUE (registration_number)
);

CREATE TABLE IF NOT EXISTS diagnosis_reports (
	id VARCHAR NOT NULL, 
	farmer_id VARCHAR, 
	farm_id VARCHAR, 
	field_id VARCHAR, 
	image_url VARCHAR(500), 
	crop VARCHAR(100), 
	disease VARCHAR(200), 
	scientific_name VARCHAR(200), 
	confidence FLOAT, 
	severity VARCHAR(50), 
	evidence JSON, 
	organic_treatment JSON, 
	chemical_treatment JSON, 
	dosage JSON, 
	prevention JSON, 
	spray_window VARCHAR(200), 
	expected_recovery_days INTEGER, 
	warnings JSON, 
	model VARCHAR(100), 
	model_version VARCHAR(20), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(farmer_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(farm_id) REFERENCES farms (id) ON DELETE SET NULL, 
	FOREIGN KEY(field_id) REFERENCES fields (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS logistics_trips (
	id VARCHAR NOT NULL, 
	farmer_id VARCHAR, 
	driver_id VARCHAR, 
	vehicle_id VARCHAR, 
	status tripstatus, 
	crop_type VARCHAR(100), 
	quantity_tons FLOAT, 
	pickup_address VARCHAR(255), 
	pickup_lat FLOAT, 
	pickup_lon FLOAT, 
	dest_address VARCHAR(255), 
	dest_lat FLOAT, 
	dest_lon FLOAT, 
	distance_km FLOAT, 
	estimated_duration_mins INTEGER, 
	base_fare FLOAT, 
	distance_fare FLOAT, 
	fuel_component FLOAT, 
	toll_estimate FLOAT, 
	loading_charge FLOAT, 
	unloading_charge FLOAT, 
	platform_fee FLOAT, 
	total_price FLOAT, 
	driver_net_earnings FLOAT, 
	pickup_time TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	cancelled_reason VARCHAR(255), 
	rating_by_farmer FLOAT, 
	review_by_farmer TEXT, 
	routing_source VARCHAR(100), 
	trip_pin VARCHAR(6), 
	accepted_at TIMESTAMP WITH TIME ZONE, 
	started_at TIMESTAMP WITH TIME ZONE, 
	driver_arrived_at TIMESTAMP WITH TIME ZONE, 
	sos_triggered BOOLEAN, 
	share_token VARCHAR(64), 
	polyline TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(farmer_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(driver_id) REFERENCES drivers (id) ON DELETE SET NULL, 
	FOREIGN KEY(vehicle_id) REFERENCES vehicles (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mart_harvest_demands (
	id VARCHAR NOT NULL, 
	offer_id VARCHAR NOT NULL, 
	customer_id VARCHAR, 
	pincode VARCHAR(10) NOT NULL, 
	quantity FLOAT NOT NULL, 
	contact_phone VARCHAR(20) NOT NULL, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(offer_id) REFERENCES mart_harvest_offers (id) ON DELETE CASCADE, 
	FOREIGN KEY(customer_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mart_order_items (
	id VARCHAR NOT NULL, 
	order_id VARCHAR NOT NULL, 
	listing_id VARCHAR NOT NULL, 
	item_title VARCHAR(150) NOT NULL, 
	unit VARCHAR(20) NOT NULL, 
	unit_price_minor INTEGER NOT NULL, 
	quantity FLOAT NOT NULL, 
	total_minor INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES mart_orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(listing_id) REFERENCES mart_listings (id)
);

CREATE TABLE IF NOT EXISTS mart_order_status_history (
	id VARCHAR NOT NULL, 
	order_id VARCHAR NOT NULL, 
	from_status VARCHAR(30), 
	to_status VARCHAR(30) NOT NULL, 
	actor_id VARCHAR, 
	actor_role VARCHAR(50), 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES mart_orders (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mart_product_reviews (
	id VARCHAR NOT NULL, 
	order_id VARCHAR NOT NULL, 
	listing_id VARCHAR NOT NULL, 
	customer_id VARCHAR NOT NULL, 
	seller_id VARCHAR NOT NULL, 
	rating INTEGER NOT NULL, 
	comment TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES mart_orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(listing_id) REFERENCES mart_listings (id) ON DELETE CASCADE, 
	FOREIGN KEY(customer_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(seller_id) REFERENCES mart_seller_profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mart_saved_items (
	id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	listing_id VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(listing_id) REFERENCES mart_listings (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS payment_transactions (
	id VARCHAR NOT NULL, 
	order_id VARCHAR NOT NULL, 
	user_id VARCHAR NOT NULL, 
	amount_minor INTEGER NOT NULL, 
	currency VARCHAR(10) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	provider VARCHAR(30) NOT NULL, 
	provider_payment_id VARCHAR(100), 
	provider_signature VARCHAR(255), 
	error_code VARCHAR(50), 
	error_description VARCHAR(255), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES payment_orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (provider_payment_id)
);

CREATE TABLE IF NOT EXISTS diagnosis_images (
	id VARCHAR NOT NULL, 
	report_id VARCHAR, 
	file_path VARCHAR(500), 
	file_size_bytes INTEGER, 
	mime_type VARCHAR(50), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(report_id) REFERENCES diagnosis_reports (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS driver_locations (
	id VARCHAR NOT NULL, 
	driver_id VARCHAR, 
	trip_id VARCHAR, 
	lat FLOAT NOT NULL, 
	lon FLOAT NOT NULL, 
	accuracy_m FLOAT, 
	heading_deg FLOAT, 
	speed_kmh FLOAT, 
	altitude_m FLOAT, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(driver_id) REFERENCES drivers (id) ON DELETE CASCADE, 
	FOREIGN KEY(trip_id) REFERENCES logistics_trips (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fare_calculations (
	id VARCHAR NOT NULL, 
	trip_id VARCHAR, 
	distance_km FLOAT, 
	duration_mins INTEGER, 
	routing_source VARCHAR(100), 
	base_fare FLOAT, 
	distance_fare FLOAT, 
	fuel_cost FLOAT, 
	fuel_price_per_liter FLOAT, 
	fuel_liters FLOAT, 
	toll_estimate FLOAT, 
	loading_charge FLOAT, 
	unloading_charge FLOAT, 
	platform_fee FLOAT, 
	surge_multiplier FLOAT, 
	total_farmer_price FLOAT, 
	driver_net_earnings FLOAT, 
	price_per_quintal FLOAT, 
	calculated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(trip_id) REFERENCES logistics_trips (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trip_events (
	id VARCHAR NOT NULL, 
	trip_id VARCHAR, 
	actor_id VARCHAR, 
	actor_role VARCHAR(20), 
	from_status VARCHAR(50), 
	to_status VARCHAR(50) NOT NULL, 
	note VARCHAR(500), 
	lat FLOAT, 
	lon FLOAT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(trip_id) REFERENCES logistics_trips (id) ON DELETE CASCADE
);

-- ============================================================================
-- PHASE 7 SECURITY HARDENING: SUPABASE POSTGRESQL ROW-LEVEL SECURITY (RLS)
-- Enforces default-deny across all 55 public tables for PostgREST / anon key
-- while allowing authenticated users to access only their own records and
-- public catalog tables to be read safely. Backend service_role / postgres
-- connection continues to operate with full administrative privileges.
-- ============================================================================

ALTER TABLE ai_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE drone_operators ENABLE ROW LEVEL SECURITY;
ALTER TABLE government_schemes ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE marketplace_sellers ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_webhook_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_feature_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE weather_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_access_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE agro_gpt_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_context ENABLE ROW LEVEL SECURITY;
ALTER TABLE broadcast_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE carbon_credits ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE drivers ENABLE ROW LEVEL SECURITY;
ALTER TABLE farms ENABLE ROW LEVEL SECURITY;
ALTER TABLE marketplace_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_catalog_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_seller_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_service_regions ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_waitlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_features ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_plan_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agro_gpt_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE driver_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE farm_crops ENABLE ROW LEVEL SECURITY;
ALTER TABLE fields ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_bulk_buying_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_harvest_offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_entitlements ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE diagnosis_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE logistics_trips ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_harvest_demands ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_order_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_product_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE mart_saved_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE diagnosis_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE driver_locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE fare_calculations ENABLE ROW LEVEL SECURITY;
ALTER TABLE trip_events ENABLE ROW LEVEL SECURITY;

-- Public read-only reference / catalog tables
CREATE POLICY "Public read government_schemes" ON government_schemes FOR SELECT USING (is_active = TRUE);
CREATE POLICY "Public read market_prices" ON market_prices FOR SELECT USING (TRUE);
CREATE POLICY "Public read mart_categories" ON mart_categories FOR SELECT USING (is_active = TRUE);
CREATE POLICY "Public read mart_catalog_items" ON mart_catalog_items FOR SELECT USING (is_active = TRUE);
CREATE POLICY "Public read mart_listings" ON mart_listings FOR SELECT USING (status = 'active');
CREATE POLICY "Public read mart_service_regions" ON mart_service_regions FOR SELECT USING (is_active = TRUE);
CREATE POLICY "Public read subscription_plans" ON subscription_plans FOR SELECT USING (status = 'active');
CREATE POLICY "Public read broadcast_items" ON broadcast_items FOR SELECT USING (status = 'published');

-- Authenticated user self-owned data policies (auth.uid()::text matches user_id / id)
CREATE POLICY "Users read own profile" ON users FOR SELECT TO authenticated USING (id = (SELECT auth.uid()::text));
CREATE POLICY "Users update own profile" ON users FOR UPDATE TO authenticated USING (id = (SELECT auth.uid()::text)) WITH CHECK (id = (SELECT auth.uid()::text));

CREATE POLICY "Users manage own farms" ON farms FOR ALL TO authenticated USING (user_id = (SELECT auth.uid()::text)) WITH CHECK (user_id = (SELECT auth.uid()::text));
CREATE POLICY "Users manage own diagnosis_reports" ON diagnosis_reports FOR ALL TO authenticated USING (user_id = (SELECT auth.uid()::text)) WITH CHECK (user_id = (SELECT auth.uid()::text));
CREATE POLICY "Users manage own agro_gpt_conversations" ON agro_gpt_conversations FOR ALL TO authenticated USING (user_id = (SELECT auth.uid()::text)) WITH CHECK (user_id = (SELECT auth.uid()::text));
CREATE POLICY "Users manage own mart_saved_items" ON mart_saved_items FOR ALL TO authenticated USING (user_id = (SELECT auth.uid()::text)) WITH CHECK (user_id = (SELECT auth.uid()::text));
CREATE POLICY "Users read own mart_orders" ON mart_orders FOR SELECT TO authenticated USING (buyer_user_id = (SELECT auth.uid()::text));
CREATE POLICY "Users read own payment_orders" ON payment_orders FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()::text));
CREATE POLICY "Users read own payment_transactions" ON payment_transactions FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()::text));
CREATE POLICY "Users read own subscriptions" ON user_subscriptions FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()::text));
CREATE POLICY "Users read own data_requests" ON data_requests FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()::text));
