-- Secret-gated analytics read function for the private dashboard page.
-- Paste into Supabase -> SQL Editor -> Run. Safe to run more than once.
--
-- WHY a secret: page_views / click_events are insert-only to the public (anon)
-- key by RLS, so the browser can log hits but cannot read them back. This
-- SECURITY DEFINER function computes aggregates, and returns them only to a
-- caller holding the secret token. Returns counts only - never a raw row.
--
-- THE TOKEN IS NEVER IN THIS FILE. The function you already have checks the
-- token in its own body. The first run of this file renames that function
-- to analytics_gate (callable by nobody but this one) and the new
-- analytics_report asks it whether a token is right. So updating the report
-- never means pasting the token anywhere, and the repository (public) never
-- holds it.
--
-- Fresh database with no analytics_report yet: create the gate by hand once,
-- with the real token in place of YOUR-TOKEN, then run this file:
--   create function public.analytics_gate(p_secret text, a date, b date, c text)
--   returns json language sql as $$ select case when p_secret = 'YOUR-TOKEN'
--     then '{}'::json else '{"error":"unauthorized"}'::json end $$;
--
-- WHAT IT RETURNS (2026-10-19 version)
--   totals, daily, top_pages, top_clicks  - as before
--   top_referrers  - where visitors CAME FROM: the referring site's host,
--                    or "(direct)". Navigation inside the site is left out;
--                    it used to fill this table with mygoldrates.com URLs.
--   top_hosts      - which hostname served the view (www vs apex check).
--                    The function in the database predated this, so the
--                    dashboard's host table was always empty.
--   lifetime       - all-time page views and visitors from page_views, so
--                    the "all time" tile counts every page, not only the
--                    pages that bump the older `hits` counter.
-- Health probes and test traffic (paths starting /__, and the probe, health
-- and test.local hosts) are excluded from every figure.

do $$
begin
  if to_regprocedure('public.analytics_gate(text,date,date,text)') is null then
    if to_regprocedure('public.analytics_report(text,date,date,text)') is null then
      raise exception 'No analytics_report to take the token from. See the '
        'note at the top of this file for a fresh database.';
    end if;
    alter function public.analytics_report(text,date,date,text)
      rename to analytics_gate;
  end if;
end $$;

revoke all on function public.analytics_gate(text,date,date,text)
  from public, anon, authenticated;

create or replace function public.analytics_report(
  p_secret text,
  p_from   date default null,
  p_to     date default null,
  p_page   text default null
) returns json
language plpgsql
security definer
set search_path = public
as $$
declare
  v_from date := coalesce(p_from, (now() at time zone 'Asia/Kolkata')::date - 13);
  v_to   date := coalesce(p_to,   (now() at time zone 'Asia/Kolkata')::date);
  v_out  json;
begin
  -- The old function answers {"error": ...} to a wrong token. '__gate__' is a
  -- page that never exists, so the check reads next to nothing.
  if p_secret is null
     or (public.analytics_gate(p_secret, v_to, v_to, '__gate__') ->> 'error') is not null then
    return json_build_object('error', 'unauthorized');
  end if;

  with pv as (
    select * from page_views
    where day between v_from and v_to
      and (p_page is null or page = p_page)
      and page not like '/\_\_%'
      and coalesce(host, '') not like 'health.%'
      and coalesce(host, '') not like 'probe.%'
      and coalesce(host, '') <> 'test.local'
  ), ce as (
    select * from click_events
    where day between v_from and v_to
      and (p_page is null or page = p_page)
      and page not like '/\_\_%'
  ), src as (
    select case
             when coalesce(referrer, '') = '' then '(direct)'
             else coalesce(lower(substring(referrer from '^[a-zA-Z]+://([^/:?#]+)')),
                           '(other)')
           end as source
    from pv
  )
  select json_build_object(
    'from', v_from,
    'to',   v_to,
    'page_filter', p_page,
    'version', '2026-10-19',
    'totals', json_build_object(
      'views',    (select count(*) from pv),
      'visitors', (select count(distinct session_id) from pv),
      'clicks',   (select count(*) from ce)),
    'daily', (
      select coalesce(json_agg(row_to_json(t) order by t.day), '[]'::json) from (
        select day::text as day, count(*) as views,
               count(distinct session_id) as visitors
        from pv group by day) t),
    'top_pages', (
      select coalesce(json_agg(row_to_json(t)), '[]'::json) from (
        select page, count(*) as views, count(distinct session_id) as visitors
        from pv group by page order by count(*) desc limit 40) t),
    'top_clicks', (
      select coalesce(json_agg(row_to_json(t)), '[]'::json) from (
        select target, count(*) as clicks
        from ce group by target order by count(*) desc limit 40) t),
    'top_referrers', (
      select coalesce(json_agg(row_to_json(t)), '[]'::json) from (
        select source as referrer, count(*) as views
        from src where source not like '%mygoldrates%'
        group by source order by count(*) desc limit 20) t),
    'top_hosts', (
      select coalesce(json_agg(row_to_json(t)), '[]'::json) from (
        select coalesce(nullif(host, ''), '(unknown)') as host, count(*) as views
        from pv group by 1 order by count(*) desc limit 10) t),
    'lifetime', (
      select json_build_object('views', count(*),
                               'visitors', count(distinct session_id),
                               'since', min(day)::text)
      from page_views
      where page not like '/\_\_%'
        and coalesce(host, '') not like 'health.%'
        and coalesce(host, '') not like 'probe.%'
        and coalesce(host, '') <> 'test.local'),
    'pages_list', (
      select coalesce(json_agg(page order by page), '[]'::json) from (
        select distinct page from page_views
        where day between v_from and v_to and page not like '/\_\_%') p)
  ) into v_out;

  return v_out;
end $$;

revoke all on function public.analytics_report(text,date,date,text) from public;
grant execute on function public.analytics_report(text,date,date,text) to anon;

-- Check: should say 'unauthorized' (wrong token on purpose).
select public.analytics_report('wrong-token');
