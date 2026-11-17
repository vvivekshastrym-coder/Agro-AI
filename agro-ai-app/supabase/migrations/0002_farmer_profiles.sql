-- 0002_farmer_profiles.sql
-- Agro AI Farmer Profiles, Farms, and Crops Schema with Strict Row-Level Security
-- Migration adheres to Supabase RLS and security best practices

-- 1. Farmer Profiles Table
create table if not exists public.farmer_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null,
  language text not null default 'English',
  state text,
  district text,
  taluk text,
  village text,
  notification_preferences jsonb not null default '{"sms": true, "whatsapp": true, "weather_alerts": true}'::jsonb,
  onboarding_status text not null default 'draft' check (onboarding_status in ('draft', 'complete')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 2. Farms Table (supports multiple land parcels per farmer)
create table if not exists public.farms (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null default 'Main Farm',
  farming_types text[] not null default '{}',
  area_value numeric(10, 2),
  area_unit text check (area_unit in ('acres', 'hectares', 'guntas')),
  ownership text check (ownership in ('own', 'leased', 'tenant')),
  irrigation text[] not null default '{}',
  created_at timestamptz not null default now()
);

-- 3. Farm Crops Table (crops grown on each farm)
create table if not exists public.farm_crops (
  id uuid primary key default gen_random_uuid(),
  farm_id uuid not null references public.farms(id) on delete cascade,
  crop_name text not null,
  area_value numeric(10, 2),
  sown_on date,
  created_at timestamptz not null default now()
);

-- Indexes for performance
create index if not exists farmer_profiles_village_idx on public.farmer_profiles (village);
create index if not exists farms_user_idx on public.farms (user_id);
create index if not exists farm_crops_farm_idx on public.farm_crops (farm_id);

-- Enable Row-Level Security on all tables
alter table public.farmer_profiles enable row level security;
alter table public.farms enable row level security;
alter table public.farm_crops enable row level security;

-- RLS Policies for farmer_profiles (Authenticated user can only access their own profile)
create policy "farmer_profiles_select_own" on public.farmer_profiles
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "farmer_profiles_insert_own" on public.farmer_profiles
  for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy "farmer_profiles_update_own" on public.farmer_profiles
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "farmer_profiles_delete_own" on public.farmer_profiles
  for delete to authenticated
  using ((select auth.uid()) = user_id);

-- RLS Policies for farms (Authenticated user can only access their own farms)
create policy "farms_select_own" on public.farms
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "farms_insert_own" on public.farms
  for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy "farms_update_own" on public.farms
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "farms_delete_own" on public.farms
  for delete to authenticated
  using ((select auth.uid()) = user_id);

-- RLS Policies for farm_crops (Accessed via farm ownership check)
create policy "farm_crops_select_own" on public.farm_crops
  for select to authenticated
  using (
    farm_id in (select id from public.farms where user_id = (select auth.uid()))
  );

create policy "farm_crops_insert_own" on public.farm_crops
  for insert to authenticated
  with check (
    farm_id in (select id from public.farms where user_id = (select auth.uid()))
  );

create policy "farm_crops_update_own" on public.farm_crops
  for update to authenticated
  using (
    farm_id in (select id from public.farms where user_id = (select auth.uid()))
  )
  with check (
    farm_id in (select id from public.farms where user_id = (select auth.uid()))
  );

create policy "farm_crops_delete_own" on public.farm_crops
  for delete to authenticated
  using (
    farm_id in (select id from public.farms where user_id = (select auth.uid()))
  );

-- Grants for Data API
grant select, insert, update, delete on public.farmer_profiles to authenticated;
grant select, insert, update, delete on public.farms to authenticated;
grant select, insert, update, delete on public.farm_crops to authenticated;

-- Automatic updated_at trigger for farmer_profiles
create or replace function public.handle_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists set_farmer_profiles_updated_at on public.farmer_profiles;
create trigger set_farmer_profiles_updated_at
  before update on public.farmer_profiles
  for each row execute function public.handle_updated_at();
