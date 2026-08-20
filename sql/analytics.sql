-- Visitor analytics: day-wise page views + click events.
-- Paste into the Supabase SQL Editor and run once.
--
-- Design notes:
--  * anon (the site's public key) may INSERT only. It cannot read anyone's
--    data back, so no visitor can enumerate the traffic log from the browser.
--  * You read the rollups below with the service key (SQL Editor is already
--    service-role) for your own analysis.
--  * `day` is a generated IST calendar date so you can group by day directly
--    without timezone math (server stores created_at in UTC).

-- ---------- page_views ----------
create table if not exists public.page_views (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  day         date generated always as
                ((created_at at time zone 'Asia/Kolkata')::date) stored,
  page        text not null,
  referrer    text,
  session_id  text
);
create index if not exists page_views_day_idx  on public.page_views(day);
create index if not exists page_views_page_idx on public.page_views(page);

-- host: added to verify the www->apex redirect (cf-redirect.yml) is actually
-- working - before the redirect, both mygoldrates.com and www.mygoldrates.com
-- served live content with no canonicalizing redirect between them, which is
-- exactly the kind of split GSC's "Duplicate, Google chose different
-- canonical" status flags. Watch this column: www hits should drop to ~0
-- once the redirect is live and browsers/crawlers stop landing on it
-- directly. Nullable/backfill-free - older rows just show null, harmless.
alter table public.page_views add column if not exists host text;
create index if not exists page_views_host_idx on public.page_views(host);

-- ---------- click_events ----------
create table if not exists public.click_events (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  day         date generated always as
                ((created_at at time zone 'Asia/Kolkata')::date) stored,
  page        text not null,
  target      text not null,
  session_id  text
);
create index if not exists click_events_day_idx    on public.click_events(day);
create index if not exists click_events_target_idx on public.click_events(target);

-- ---------- RLS: anon may insert, nobody may read via the public key ----------
alter table public.page_views  enable row level security;
alter table public.click_events enable row level security;

drop policy if exists pv_anon_insert on public.page_views;
create policy pv_anon_insert on public.page_views
  for insert to anon with check (true);

drop policy if exists ce_anon_insert on public.click_events;
create policy ce_anon_insert on public.click_events
  for insert to anon with check (true);

-- ================= rollups for your analysis =================

-- Daily total hits (page views) and unique sessions, newest first.
create or replace view public.daily_hits as
select day,
       count(*)                          as page_views,
       count(distinct session_id)        as unique_visitors
from public.page_views
group by day
order by day desc;

-- Daily most-viewed pages (top pages per day).
create or replace view public.daily_top_pages as
select day, page, count(*) as views
from public.page_views
group by day, page
order by day desc, views desc;

-- Daily most-clicked elements (what people actually tap).
create or replace view public.daily_top_clicks as
select day, target, count(*) as clicks
from public.click_events
group by day, target
order by day desc, clicks desc;
