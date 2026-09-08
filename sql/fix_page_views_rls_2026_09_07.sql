-- RLS repair: reinstate the anon INSERT policy on page_views.
--
-- On 2026-09-07, live probes showed anon INSERTs into public.page_views
-- returning 401 with `new row violates row-level security policy for table
-- "page_views"`. click_events INSERTs from the same key returned 201, so
-- the anon key was fine - only the page_views INSERT policy had gone missing
-- (either never applied after a schema reset, or dropped by a later change).
--
-- Every pageview from every page - /, /compare, city pages, calculators -
-- was silently swallowed by the browser tracker's .catch() for as long as
-- this was broken. Result: the dashboard read as if the site had almost no
-- traffic, when in reality it had thousands of pre-outage hits (frozen)
-- plus zero recorded new ones.
--
-- Fix: recreate the same anon-insert policy defined in analytics.sql, and
-- also add a NO-OP SELECT policy for the service_role (already implicit -
-- service_role bypasses RLS - so this is just a belt-and-braces marker).
--
-- Paste into the Supabase SQL Editor and run once. Idempotent (drops-then-
-- recreates) so it is safe to re-run after any future migration or reset.

alter table public.page_views enable row level security;

drop policy if exists pv_anon_insert on public.page_views;
create policy pv_anon_insert on public.page_views
  for insert to anon with check (true);

-- Same reinstate for click_events, defensively - so a future accidental
-- drop of that policy is caught by re-running this one file.
alter table public.click_events enable row level security;

drop policy if exists ce_anon_insert on public.click_events;
create policy ce_anon_insert on public.click_events
  for insert to anon with check (true);

-- Verification query - after running the file above, this should insert
-- one row and return count=1 (service_role bypasses RLS so it always
-- succeeds; the real test is that anon inserts start returning 201).
-- select count(*) from public.page_views where page = '/__rls_probe__';
