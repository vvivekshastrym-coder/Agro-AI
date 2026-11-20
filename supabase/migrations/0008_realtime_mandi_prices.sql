-- Agro AI Real-Time Mandi Markets Migration
-- Creates the authoritative mandi_prices table with unique constraints, indexes, and Supabase RLS.

CREATE TABLE IF NOT EXISTS public.mandi_prices (
  id TEXT PRIMARY KEY,
  commodity VARCHAR(100) NOT NULL,
  market VARCHAR(150) NOT NULL,
  district VARCHAR(100) NOT NULL,
  state VARCHAR(100) NOT NULL,
  min_price DOUBLE PRECISION NOT NULL CHECK (min_price >= 0),
  max_price DOUBLE PRECISION NOT NULL CHECK (max_price >= 0),
  modal_price DOUBLE PRECISION NOT NULL CHECK (modal_price >= 0),
  currency VARCHAR(10) NOT NULL DEFAULT 'INR',
  unit VARCHAR(20) NOT NULL DEFAULT 'quintal',
  arrival_quantity DOUBLE PRECISION,
  arrival_unit VARCHAR(20) DEFAULT 'quintal',
  market_date VARCHAR(10) NOT NULL,
  source_name VARCHAR(100) NOT NULL,
  source_url VARCHAR(500),
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  verification_status VARCHAR(30) NOT NULL DEFAULT 'verified',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_price_order CHECK (min_price <= max_price),
  CONSTRAINT uq_mandi_prices_entry UNIQUE (commodity, market, market_date, unit, source_name)
);

CREATE INDEX IF NOT EXISTS ix_mandi_prices_commodity ON public.mandi_prices(commodity);
CREATE INDEX IF NOT EXISTS ix_mandi_prices_market ON public.mandi_prices(market);
CREATE INDEX IF NOT EXISTS ix_mandi_prices_district ON public.mandi_prices(district);
CREATE INDEX IF NOT EXISTS ix_mandi_prices_state ON public.mandi_prices(state);
CREATE INDEX IF NOT EXISTS ix_mandi_prices_market_date ON public.mandi_prices(market_date);
CREATE INDEX IF NOT EXISTS ix_mandi_prices_lookup ON public.mandi_prices(commodity, market, market_date);

-- Enable Row Level Security (RLS)
ALTER TABLE public.mandi_prices ENABLE ROW LEVEL SECURITY;

-- Public users can only read approved/verified market price records
DROP POLICY IF EXISTS mandi_prices_public_read ON public.mandi_prices;
CREATE POLICY mandi_prices_public_read ON public.mandi_prices
  FOR SELECT USING (verification_status IN ('verified', 'provisional', 'flagged_conflict'));

-- Only backend service_role / administrators can insert, update, or delete
DROP POLICY IF EXISTS mandi_prices_admin_write ON public.mandi_prices;
CREATE POLICY mandi_prices_admin_write ON public.mandi_prices
  FOR ALL TO authenticated USING (
    EXISTS (
      SELECT 1 FROM public.users
      WHERE users.id = auth.uid()::text
      AND users.role IN ('admin', 'super_admin')
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.users
      WHERE users.id = auth.uid()::text
      AND users.role IN ('admin', 'super_admin')
    )
  );
