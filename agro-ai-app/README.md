# Agro AI — real working app (MVP)

A deployable web app for the Agro AI must-have tier: **Agro GPT, Diagnose, Weather, Mandi Market, Pest Radar** — plus email sign-in and per-farmer history. Built with React + Vite + Tailwind on the frontend, Supabase for auth/database, and Supabase Edge Functions as a secure server-side proxy for the AI calls (so no API key ever reaches the browser).

## What's real here (and what isn't yet)

| Feature | Status |
|---|---|
| Auth (email magic link) | Real — Supabase Auth |
| Agro GPT chat | Real — Claude via a server-side Edge Function |
| Leaf Diagnose | Real — Claude vision via a server-side Edge Function |
| Weather | Real — free Open-Meteo API, no key needed |
| Mandi Market | Real — data.gov.in AGMARKNET government price data, summarized by Claude. Shows "no data" honestly if a crop/state combo has no recent records, rather than inventing a price |
| Pest Radar | Real — farmer-submitted reports stored in your database, aggregated by village. No outbreak data is fabricated; it starts empty until real farmers report |
| Inputs, Logistics, Credit, Drone, Satellite, Carbon, Insurance, Soil DNA, Passport | Not built — shown honestly as "Soon" in the More screen. These need extra integrations (Google Maps, Sentinel-2/Earth Engine, a payments/insurance partner, a physical lab) that are bigger, separate projects |
| Voice AI / WhatsApp bot / 50-dialect Bhashini pipeline | Not built — needs Twilio/Exotel + Bhashini server-side integration, out of scope for a browser app |

## 1. Install

```bash
npm install
```

## 2. Connect your Supabase project (frontend)

```bash
cp .env.example .env
```

Fill in `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` from **Project Settings → API** in your Supabase dashboard. Both are safe to put in the frontend.

## 3. Set up the database

Install the Supabase CLI if you don't have it (`npm install -g supabase`), then from this folder:

```bash
supabase link --project-ref YOUR-PROJECT-REF
supabase db push
```

This creates the `diagnoses`, `chat_messages`, and `pest_reports` tables with row-level security (see `supabase/migrations/0001_init.sql`). If you'd rather not use the CLI, just paste that file's contents into the SQL Editor in your Supabase dashboard and run it.

Enable **Email** auth under Authentication → Providers if it isn't already on (it is by default).

## 4. Deploy the Edge Functions (this is where your AI key lives — never in the frontend)

```bash
supabase functions deploy agro-chat
supabase functions deploy diagnose-leaf
supabase functions deploy mandi-price
```

Then set the secrets they read from:

```bash
supabase secrets set ANTHROPIC_API_KEY=sk-ant-your-key-here
supabase secrets set DATA_GOV_API_KEY=your-datagovin-key-here
```

- Get an Anthropic API key at https://console.anthropic.com (needed for chat + diagnose + the mandi price summary).
- Get a free data.gov.in API key at https://data.gov.in (needed for real mandi prices — sign up, generate a key from your profile page). If you skip this, Mandi Market will honestly show "not configured yet" instead of a fake price.

## 5. Run it locally

```bash
npm run dev
```

Open the printed localhost URL on your phone (same wifi) or in a mobile-width browser window to see the app as farmers would.

## 6. Deploy the frontend

Any static host works (it's a Vite build). Simplest options:

**Vercel**
```bash
npm i -g vercel
vercel
```
Add `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` as project env vars in the Vercel dashboard.

**Netlify**
```bash
npm run build
# drag the dist/ folder into netlify.com/drop, or:
netlify deploy --prod --dir=dist
```

## Project structure

```
src/
  pages/         Home, Diagnose, AgroGPT, Weather, Market, PestRadar, More, Login
  components/    Shell.tsx (top bar, language pills, bottom nav)
  lib/           supabaseClient, ai.ts (edge function + Open-Meteo calls), useAuth, AppContext
supabase/
  migrations/    SQL schema + RLS policies
  functions/     agro-chat, diagnose-leaf, mandi-price (Deno Edge Functions)
```

## Design system

Matches the Agro AI Feature & UI Spec: Forest Green `#1F4D2B` / Saffron `#E58A2D` / Cream `#FFF8EC` / Leaf `#3F7A3F` / Ink `#1A1A1A`, Fraunces (display) + Inter (body), rounded-3xl cards, pill buttons, fixed bottom tab bar (Home · Diagnose · Agro GPT · Weather · More).

## Honest next steps, in rough order

1. Add more languages to the AI prompts' output validation (right now the model is *asked* to reply in the selected language — for guaranteed-accurate regional script, add Bhashini as a translation layer).
2. Add photo upload to Pest Reports (Supabase Storage — a `pest-photos` bucket, few lines of code) so reports carry visual evidence.
3. Wrap with Capacitor for an installable Android app once the web version is validated with real farmers.
4. Mandi price forecasting (30-day, not just latest) needs either a proper time-series model over historical AGMARKNET pulls, or a paid forecasting API — the current version summarizes real recent records rather than projecting forward, to avoid presenting a guess as a forecast.
