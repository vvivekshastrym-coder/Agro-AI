-- Agro AI initial schema
-- Run with: supabase db push  (or paste into the SQL editor in the Supabase dashboard)

create table if not exists public.diagnoses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  crop_hint text,
  severity text not null,
  report text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  created_at timestamptz not null default now()
);

-- Pest reports are intentionally open (user_id nullable) so that even a
-- quick anonymous report from the field is captured — but reads are public
-- so the whole village benefits, per Agro AI's "never fabricate" principle:
-- Pest Radar only ever shows real, farmer-submitted reports.
create table if not exists public.pest_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  crop text not null,
  symptom text not null,
  village text not null,
  created_at timestamptz not null default now()
);

alter table public.diagnoses enable row level security;
alter table public.chat_messages enable row level security;
alter table public.pest_reports enable row level security;

-- Diagnoses: a farmer can only see and insert their own history.
create policy "diagnoses_select_own" on public.diagnoses
  for select using (auth.uid() = user_id);
create policy "diagnoses_insert_own" on public.diagnoses
  for insert with check (auth.uid() = user_id);

-- Chat messages: same, private per farmer.
create policy "chat_select_own" on public.chat_messages
  for select using (auth.uid() = user_id);
create policy "chat_insert_own" on public.chat_messages
  for insert with check (auth.uid() = user_id);

-- Pest reports: readable by anyone signed in (it's a shared village radar),
-- insertable by anyone signed in.
create policy "pest_reports_select_all" on public.pest_reports
  for select using (auth.role() = 'authenticated');
create policy "pest_reports_insert_all" on public.pest_reports
  for insert with check (auth.role() = 'authenticated');

create index if not exists pest_reports_village_idx on public.pest_reports (village);
create index if not exists diagnoses_user_idx on public.diagnoses (user_id);
create index if not exists chat_messages_user_idx on public.chat_messages (user_id);
