-- Migration: 0004_government_schemes.sql
-- Description: Authentic Central & State Government Agricultural Schemes & Subsidies with Profile Eligibility Matching

CREATE TABLE IF NOT EXISTS government_schemes (
    id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    short_description TEXT NOT NULL,
    benefit_summary TEXT NOT NULL,
    benefit_amount TEXT,
    category TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'central',
    state TEXT,
    min_land_acres NUMERIC DEFAULT 0.0,
    max_land_acres NUMERIC,
    eligible_crops JSONB DEFAULT '[]'::jsonb,
    eligible_farmer_types JSONB DEFAULT '[]'::jsonb,
    eligible_states JSONB DEFAULT '[]'::jsonb,
    application_portal TEXT NOT NULL,
    application_process TEXT,
    required_documents JSONB DEFAULT '[]'::jsonb,
    key_highlights JSONB DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE government_schemes ENABLE ROW LEVEL SECURITY;

-- Read policy: Anyone (farmers, guests, public) can read active schemes
CREATE POLICY "Public can view active government schemes"
    ON government_schemes
    FOR SELECT
    USING (is_active = true);

-- Write policy: Only admins can manage government schemes
CREATE POLICY "Admins can manage government schemes"
    ON government_schemes
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM admin_users
            WHERE admin_users.user_id = auth.uid()
            AND admin_users.is_active = true
            AND admin_users.role IN ('super_admin', 'content_manager')
        )
    );

-- Seed Authentic Real Government Schemes
INSERT INTO government_schemes (
    id, slug, title, short_description, benefit_summary, benefit_amount,
    category, level, state, min_land_acres, max_land_acres, eligible_crops,
    application_portal, required_documents, key_highlights, is_active
) VALUES
(
    gen_random_uuid()::text,
    'pm-kisan',
    'Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)',
    'Direct income support of ₹6,000 per year directly to bank accounts in three 4-monthly installments.',
    '₹6,000 / year Direct Cash Transfer (DBT)',
    '₹6,000 / year',
    'Direct Income Support',
    'central',
    NULL,
    0.0,
    NULL,
    '[]'::jsonb,
    'https://pmkisan.gov.in',
    '["Aadhaar Card", "Land Record (RTC / 7-12 / Khatauni)", "Aadhaar-seeded Bank Account (NPCI enabled)"]'::jsonb,
    '["100% centrally funded DBT scheme", "No middlemen or commissions", "Over 11 crore farmers supported"]'::jsonb,
    true
),
(
    gen_random_uuid()::text,
    'pmfby-crop-insurance',
    'Pradhan Mantri Fasal Bima Yojana (PMFBY)',
    'Comprehensive crop insurance shield covering sowing to post-harvest natural risk with ultra-low farmer premiums.',
    'Comprehensive Crop Loss Insurance Coverage',
    'Up to 100% Sum Insured',
    'Crop Insurance',
    'central',
    NULL,
    0.0,
    NULL,
    '["Tomato", "Wheat", "Rice / Paddy", "Cotton", "Sugarcane", "Maize", "Onion"]'::jsonb,
    'https://pmfby.gov.in',
    '["Aadhaar Card", "Crop Sowing Certificate", "Land Record (RTC / 7-12)", "Bank Passbook showing IFSC"]'::jsonb,
    '["Max 2% premium for Kharif and 1.5% for Rabi crops", "Commercial crops capped at 5%", "Covers localized disasters and post-harvest loss"]'::jsonb,
    true
),
(
    gen_random_uuid()::text,
    'pmksy-per-drop-more-crop',
    'PM Krishi Sinchayee Yojana (PMKSY) — Drip & Sprinkler Subsidy',
    'Heavy financial subsidies for installing precision Drip and Sprinkler micro-irrigation systems.',
    'Up to 55%–80% Micro-Irrigation Subsidy',
    '55% to 80% Cost Subsidy',
    'Micro Irrigation',
    'central',
    NULL,
    0.5,
    NULL,
    '["Tomato", "Sugarcane", "Cotton", "Maize", "Onion", "Horticulture", "Vegetables"]'::jsonb,
    'https://pmksy.gov.in',
    '["Aadhaar Card", "Land RTC / 7-12 Extract (min 0.5 ac)", "Water Source Proof (Borewell / Canal)", "Vendor Quotation"]'::jsonb,
    '["55% central subsidy for Small & Marginal farmers", "State top-ups up to 75%-90% for SC/ST", "Saves 40-50% water while boosting yield"]'::jsonb,
    true
),
(
    gen_random_uuid()::text,
    'kisan-credit-card-miss',
    'Kisan Credit Card (KCC) & 4% Subsidized Crop Loan',
    'Low-interest institutional agricultural working capital credit with 3% prompt repayment incentive.',
    'Up to ₹3,00,000 Loan at 4% Interest',
    '₹1,60,000 Collateral-Free (Up to ₹3 Lakh at 4%)',
    'Agricultural Credit',
    'central',
    NULL,
    0.0,
    NULL,
    '[]'::jsonb,
    'https://www.myscheme.gov.in/schemes/kcc',
    '["KCC Application Form", "Aadhaar Card & PAN", "Land Record (RTC / 7-12)", "No Dues Certificate"]'::jsonb,
    '["Effective 4% interest rate with prompt repayment", "Collateral-free limit up to ₹1.60 lakh", "ATM-enabled RuPay Kisan Card"]'::jsonb,
    true
),
(
    gen_random_uuid()::text,
    'smam-farm-mechanization',
    'Sub-Mission on Agricultural Mechanization (SMAM)',
    '40% to 50% subsidy on purchase of tractors, power tillers, rotavators, sprayers, and combine harvesters.',
    '40% to 50% Subsidy on Farm Machinery',
    '₹40,000 to ₹2,50,000 Subsidy',
    'Farm Machinery & Mechanization',
    'central',
    NULL,
    1.0,
    NULL,
    '[]'::jsonb,
    'https://agrimachinery.nic.in',
    '["Aadhaar Card", "Land RTC (minimum 1 acre)", "Bank Passbook with IFSC", "Vendor Machinery Quotation"]'::jsonb,
    '["50% subsidy for Small, Marginal, SC/ST, and Women farmers", "40% for general category", "Up to 80% for Custom Hiring Centres"]'::jsonb,
    true
),
(
    gen_random_uuid()::text,
    'soil-health-card-scheme',
    'Soil Health Card (SHC) Nutrient Management Scheme',
    '100% Free soil testing and personalized fertilizer dosage card provided once every 2 years.',
    'Free Soil Testing & Personalized Fertilizer Dosage',
    '100% Free Advisory',
    'Soil Testing & Fertilizer Advisory',
    'central',
    NULL,
    0.0,
    NULL,
    '[]'::jsonb,
    'https://soilhealth.dac.gov.in',
    '["Aadhaar Card", "Farm Survey Number / Gut Number"]'::jsonb,
    '["Tests 12 parameters: N, P, K, S, Zn, Fe, Cu, Mn, Bo, pH, EC, OC", "Saves 15-25% chemical fertilizer cost"]'::jsonb,
    true
),
(
    gen_random_uuid()::text,
    'karnataka-raitha-siri',
    'Karnataka Raitha Siri Scheme (Millet Production Incentive)',
    'Direct cash incentive of ₹10,000 per hectare directly to Karnataka farmers growing notified minor millets.',
    '₹10,000 / hectare Direct Millet Bonus (Up to ₹20,000)',
    '₹10,000 / hectare (Max ₹20,000)',
    'Millet Cultivation Subsidy',
    'state',
    'Karnataka',
    0.5,
    5.0,
    '["Millets", "Ragi", "Fox-tail millet", "Little millet", "Kodo millet"]'::jsonb,
    'https://fruits.karnataka.gov.in',
    '["Karnataka FRUITS Farmer ID (FID)", "Pahani / RTC showing millet crop", "Aadhaar Card linked Bank Account"]'::jsonb,
    '["Karnataka State special incentive for nutri-cereals", "Direct e-Governance DBT into bank account", "Max subsidy up to 2 hectares (₹20,000)"]'::jsonb,
    true
),
(
    gen_random_uuid()::text,
    'karnataka-krishi-bhagya',
    'Karnataka Krishi Bhagya Scheme (Farm Pond & Polyhouse Subsidy)',
    '80% to 90% subsidy for construction of Farm Ponds (Krishi Honda) with polythene lining and shade net houses.',
    '80%–90% Subsidy on Farm Ponds & Water Harvesting',
    'Up to ₹1,50,000 Subsidy',
    'Water Harvesting & Farm Ponds',
    'state',
    'Karnataka',
    1.0,
    NULL,
    '[]'::jsonb,
    'https://raitamitra.karnataka.gov.in',
    '["Land RTC / Pahani", "Karnataka FRUITS ID", "Caste Certificate (for 90% rate)", "Aadhaar Card"]'::jsonb,
    '["80% subsidy for General and 90% for SC/ST farmers", "Includes polythene lining, fencing, and diesel pump sets"]'::jsonb,
    true
),
(
    gen_random_uuid()::text,
    'maharashtra-namo-shetkari',
    'Maharashtra Namo Shetkari Mahasanman Nidhi Yojana',
    'Additional ₹6,000 per year DBT top-up from Maharashtra State Government over and above PM-KISAN.',
    '₹6,000 / year Extra State DBT (Total ₹12,000/yr with PM-KISAN)',
    '₹6,000 / year',
    'Direct Income Support',
    'state',
    'Maharashtra',
    0.0,
    NULL,
    '[]'::jsonb,
    'https://mahadbt.maharashtra.gov.in',
    '["PM-KISAN Beneficiary ID", "Aadhaar Card with e-KYC", "7/12 & 8A Land Extract", "Bank Account with NPCI"]'::jsonb,
    '["Delivered in 3 quarterly installments of ₹2,000 each", "Combined ₹12,000 cash per year with PM-KISAN", "Paperless MahaDBT integration"]'::jsonb,
    true
)
ON CONFLICT (slug) DO NOTHING;
