-- Two fixes to the analytics reads. Idempotent; paste into the Supabase
-- SQL Editor and run.
--
-- 1. THE ROLLUP VIEWS ARE WORLD-READABLE.
--
--    sql/analytics.sql says, correctly, that anon may INSERT only, "so no
--    visitor can enumerate the traffic log from the browser". RLS on
--    page_views and click_events does enforce that: selecting the tables
--    with the public key returns [].
--
--    The views built on top of them do not. A PostgreSQL view runs with its
--    OWNER's privileges unless it is declared security_invoker, so
--    daily_hits, daily_top_pages and daily_top_clicks read straight past the
--    RLS policies. The anon key is in the page source of every page on the
--    site, by design, which means anybody at all can read:
--
--        GET /rest/v1/daily_hits        -> every day's traffic
--        GET /rest/v1/daily_top_pages   -> every page and its view count
--
--    Verified against production on 2026-10-09: all three returned data to
--    the public key. The base tables correctly returned nothing, which is
--    what made this easy to miss.
--
--    security_invoker makes the views honour the caller's RLS, so anon gets
--    nothing and the service key (SQL Editor) still sees everything.

alter view public.daily_hits       set (security_invoker = on);
alter view public.daily_top_pages  set (security_invoker = on);
alter view public.daily_top_clicks set (security_invoker = on);

-- 2. SYNTHETIC ROWS ARE COUNTED AS TRAFFIC.
--
--    analytics_health.py inserts a probe row into each table on every build
--    and its docstring says they "carry session_id='__health_probe__' so the
--    dashboard can filter them out". Nothing filtered them out: not the
--    views, not analytics_report. 23 probe pageviews are in the history, up
--    to 6 on a build-heavy day. Against a real figure of ~67 views/day that
--    is a few percent of the number being read off the dashboard.
--
--    Excluded at the source so every reader gets the same answer.

create or replace view public.daily_hits as
select day,
       count(*)                   as page_views,
       count(distinct session_id) as unique_visitors
from public.page_views
where page not like '/\_\_%'          -- /__health__, /__claude_probe__, ...
group by day
order by day desc;

create or replace view public.daily_top_pages as
select day, page, count(*) as views
from public.page_views
where page not like '/\_\_%'
group by day, page
order by day desc, views desc;

create or replace view public.daily_top_clicks as
select day, target, count(*) as clicks
from public.click_events
where page not like '/\_\_%'
group by day, target
order by day desc, clicks desc;

alter view public.daily_hits       set (security_invoker = on);
alter view public.daily_top_pages  set (security_invoker = on);
alter view public.daily_top_clicks set (security_invoker = on);

-- Leaves analytics_report() alone: it is SECURITY DEFINER behind a secret
-- and reads the base tables directly, so it needs the same exclusion added
-- to each of its WHERE clauses. That is a larger edit to a function whose
-- body holds the real token, so it is left for a deliberate pass rather
-- than bundled in here.

-- 3. OPTIONAL: remove the synthetic rows already in the history.
--
--    The views above exclude them from here on, but the rows remain. These
--    deletes remove only paths that no visitor can ever produce: they all
--    begin "/__".
--
--      /__health__          analytics_health.py, one per build since Sep
--      /__beacon_test__/*   measuring fetch vs keepalive, 2026-10-09
--      /__claude_probe__    one row verifying anon INSERT still works
--
--    Run them or don't - excluding them is enough for the numbers to be
--    right. Nothing else is touched.

-- delete from public.page_views   where page like '/\_\_%';
-- delete from public.click_events where page like '/\_\_%';

-- NOT removable by pattern: on 2026-10-09 a browser was driven over the
-- live site to measure when the beacon fires, which wrote ordinary-looking
-- rows against real paths (mostly /gold-rate-today-in-chennai, a few each
-- on /, /compare, /calculators and others). They are indistinguishable
-- from real visits because that was the point of the test. Roughly 35-40
-- rows, all on 2026-10-09 only. Read that one day's figures with that in
-- mind; from 2026-10-10 the numbers are clean.
