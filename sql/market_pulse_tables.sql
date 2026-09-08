-- Market Pulse persistence + the hits_today RPC.
-- Paste into the Supabase SQL Editor and run once. Idempotent.
--
-- WHY: every number on the Market Pulse homepage was, until now, either
-- fetched live from a third-party upstream on each page load or (worse)
-- read from a hardcoded snapshot in the page source. Nothing was stored,
-- so there was no history, no way to audit a bad print, and no single
-- source of truth to reconcile the page against. These tables give the
-- market data the same treatment `rates` already gives jeweller prices.
--
-- Writer: market_snapshot.py (workflow: market-snapshot.yml) pulls the
-- Cloudflare worker's /market, /vendors, /ohlc, /calendar and /news
-- endpoints and upserts here with the service key.
--
-- Readers: the dashboard and any backfill/analysis. The live page still
-- reads the worker directly for sub-second freshness - these tables are
-- the durable record behind it, not a slower path in front of it.

-- ---------- market_ticks: one row per polled market snapshot ----------
create table if not exists public.market_ticks (
  id                bigint generated always as identity primary key,
  created_at        timestamptz not null default now(),
  day               date generated always as
                      ((created_at at time zone 'Asia/Kolkata')::date) stored,
  gold_usd_oz       numeric,   -- XAU spot, USD per troy oz
  silver_usd_oz     numeric,   -- XAG spot, USD per troy oz
  usd_inr           numeric,
  gold_inr_g        numeric,   -- derived 24K INR/gram incl. India premium
  silver_inr_kg     numeric,   -- derived INR/kg incl. India premium
  mcx_gold_ltp      numeric,
  mcx_gold_expiry   text,
  mcx_gold_pchg     numeric,
  mcx_silver_ltp    numeric,
  mcx_silver_expiry text,
  mcx_silver_pchg   numeric,
  source            text not null default 'cf-worker'
);
create index if not exists market_ticks_day_idx on public.market_ticks(day);
create index if not exists market_ticks_created_idx
  on public.market_ticks(created_at desc);

-- ---------- vendor_rates: bullion dealer board rates (VOTS feed) ----------
create table if not exists public.vendor_rates (
  id         bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  day        date generated always as
               ((created_at at time zone 'Asia/Kolkata')::date) stored,
  dealer     text not null,          -- e.g. 'arihant', 'safari'
  metal      text not null,          -- 'GOLD_995' | 'GOLD_999' | 'SILVER_999'
  buy        numeric,
  sell       numeric,
  high       numeric,
  low        numeric
);
create index if not exists vendor_rates_day_idx on public.vendor_rates(day);
create index if not exists vendor_rates_dealer_idx
  on public.vendor_rates(dealer, metal);

-- ---------- ohlc_history: daily OHLC for gold/silver futures ----------
-- Keyed on (symbol, d) so a re-run of the writer corrects a day in place
-- instead of duplicating it.
create table if not exists public.ohlc_history (
  symbol     text not null,          -- 'GC=F' (gold) | 'SI=F' (silver)
  d          date not null,
  open       numeric,
  high       numeric,
  low        numeric,
  close      numeric,
  updated_at timestamptz not null default now(),
  primary key (symbol, d)
);

-- ---------- market_news: bullion headlines ----------
create table if not exists public.market_news (
  id           bigint generated always as identity primary key,
  fetched_at   timestamptz not null default now(),
  published_at timestamptz,
  title        text not null,
  url          text not null unique,  -- dedupe key across re-runs
  source       text
);
create index if not exists market_news_published_idx
  on public.market_news(published_at desc);

-- ---------- economic_calendar: gold-relevant macro events ----------
create table if not exists public.economic_calendar (
  id         bigint generated always as identity primary key,
  fetched_at timestamptz not null default now(),
  event_at   timestamptz,
  title      text not null,
  country    text,
  impact     text,                    -- High | Medium | Low
  actual     text,
  forecast   text,
  previous   text,
  unique (event_at, title, country)
);
create index if not exists economic_calendar_event_idx
  on public.economic_calendar(event_at);

-- ---------- RLS: anon may READ market data, only service_role writes ----------
-- Opposite of page_views/click_events: this is public market information
-- meant to be displayed, so anon gets SELECT and gets no INSERT at all.
-- The writer uses the service key, which bypasses RLS.
alter table public.market_ticks      enable row level security;
alter table public.vendor_rates      enable row level security;
alter table public.ohlc_history      enable row level security;
alter table public.market_news       enable row level security;
alter table public.economic_calendar enable row level security;

drop policy if exists mt_anon_read on public.market_ticks;
create policy mt_anon_read on public.market_ticks
  for select to anon using (true);

drop policy if exists vr_anon_read on public.vendor_rates;
create policy vr_anon_read on public.vendor_rates
  for select to anon using (true);

drop policy if exists oh_anon_read on public.ohlc_history;
create policy oh_anon_read on public.ohlc_history
  for select to anon using (true);

drop policy if exists mn_anon_read on public.market_news;
create policy mn_anon_read on public.market_news
  for select to anon using (true);

drop policy if exists ec_anon_read on public.economic_calendar;
create policy ec_anon_read on public.economic_calendar
  for select to anon using (true);

-- ---------- hits_today: today's visit count ----------
-- The homepage counter wants "N total views - M today". `hits` is a single
-- lifetime counter with no per-day breakdown, so "today" comes from the
-- page_views log instead (distinct sessions seen today, IST). Returns 0
-- rather than null when there is no traffic yet so the caller can format
-- it without a null check.
--
-- SECURITY DEFINER because page_views is insert-only to anon by RLS - this
-- returns a single aggregate integer, never a row, so it leaks no visitor
-- data while still being safe to call from the public page.
create or replace function public.hits_today()
returns integer
language sql
security definer
set search_path = public
as $$
  select coalesce(count(distinct session_id), 0)::int
  from public.page_views
  where day = (now() at time zone 'Asia/Kolkata')::date;
$$;

revoke all on function public.hits_today() from public;
grant execute on function public.hits_today() to anon;
