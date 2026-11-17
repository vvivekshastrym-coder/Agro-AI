-- Migration: 0007_my_land_and_applications.sql
-- Multi-parcel farmer land profiles, document metadata, and scheme application tracker with strict RLS.

CREATE TABLE IF NOT EXISTS public.land_parcels (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  farmer_name VARCHAR(120),
  fruits_id VARCHAR(64),
  state VARCHAR(60) NOT NULL DEFAULT 'Karnataka',
  district VARCHAR(80) NOT NULL,
  taluk VARCHAR(80),
  hobli VARCHAR(80),
  village VARCHAR(100),
  survey_number VARCHAR(50),
  sub_survey_number VARCHAR(30),
  rtc_reference VARCHAR(80),
  total_acres DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  cultivable_acres DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  ownership_type VARCHAR(30) NOT NULL DEFAULT 'owner',
  irrigation_source VARCHAR(40) NOT NULL DEFAULT 'rainfed',
  soil_type VARCHAR(50),
  soil_health_card_no VARCHAR(64),
  current_crop VARCHAR(80),
  crop_season VARCHAR(30) DEFAULT 'Kharif',
  sowing_date VARCHAR(20),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.land_documents (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  parcel_id TEXT REFERENCES public.land_parcels(id) ON DELETE SET NULL,
  doc_type VARCHAR(50) NOT NULL,
  title VARCHAR(150) NOT NULL,
  verification_status VARCHAR(40) NOT NULL DEFAULT 'uploaded',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.scheme_applications (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  parcel_id TEXT REFERENCES public.land_parcels(id) ON DELETE SET NULL,
  scheme_slug VARCHAR(100) NOT NULL,
  scheme_title VARCHAR(200) NOT NULL,
  application_ref VARCHAR(100),
  department VARCHAR(150),
  applied_amount VARCHAR(80),
  status VARCHAR(40) NOT NULL DEFAULT 'preparing_documents',
  status_source VARCHAR(40) NOT NULL DEFAULT 'farmer_updated',
  next_action VARCHAR(255),
  follow_up_date VARCHAR(20),
  official_portal_url VARCHAR(300),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ
);

ALTER TABLE public.land_parcels ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.land_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scheme_applications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS land_parcels_owner ON public.land_parcels;
CREATE POLICY land_parcels_owner ON public.land_parcels
  FOR ALL USING (auth.uid()::text = user_id) WITH CHECK (auth.uid()::text = user_id);

DROP POLICY IF EXISTS land_documents_owner ON public.land_documents;
CREATE POLICY land_documents_owner ON public.land_documents
  FOR ALL USING (auth.uid()::text = user_id) WITH CHECK (auth.uid()::text = user_id);

DROP POLICY IF EXISTS scheme_applications_owner ON public.scheme_applications;
CREATE POLICY scheme_applications_owner ON public.scheme_applications
  FOR ALL USING (auth.uid()::text = user_id) WITH CHECK (auth.uid()::text = user_id);
