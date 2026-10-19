-- Secret-gated analytics read function for the private dashboard page.
-- Paste into Supabase -> SQL Editor -> Run. Safe to run more than once.
-- Three blocks; each can also be pasted and run on its own, in order.
-- No backslashes or regex patterns, so a phone copy-paste cannot mangle them.
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
-- WHAT IT RETURNS (2026-10-20 version)
--   totals, daily, top_pages, top_clicks  - as before
--   top_referrers  - where visitors CAME FROM: the referring site's host,
--                    or "(direct)". Navigation inside the site is left out;
--                    it used to fill this table with mygoldrates.com URLs.
--   top_hosts      - which hostname served the view (www vs apex check).
--                    The function in the database predated this, so the
--                    dashboard's host table was always empty.
--   unsubs         - unsubscribes in the range (every one, with or without
--                    a reason), counts by reason, the 20 most recent, and
--                    how many people are subscribed right now.
--   lifetime       - all-time page views and visitors from page_views, so
--                    the "all time" tile counts every page, not only the
--                    pages that bump the older `hits` counter.
-- Health probes and test traffic (paths starting /__, and the probe, health
-- and test.local hosts) are excluded from every figure.

-- ---- Block 1: unsubscribe reasons table and its save function
create table if not exists public.unsub_reasons (
  id bigint generated always as identity primary key,
  reason text not null,
  created_at timestamptz not null default now()
);
revoke all on public.unsub_reasons from anon, authenticated;

create or replace function public.save_unsub_reason(t text, reason text)
returns void language plpgsql security definer
set search_path = public as $f$
begin
  if t is not null and exists (
    select 1 from public.inquiries where unsub_token = t
  ) then
    insert into public.unsub_reasons(reason)
    values (left(coalesce(reason, ''), 200));
  end if;
end $f$;

grant execute on function public.save_unsub_reason(text, text)
  to anon, authenticated;

-- ---- Block 2: keep the existing token check as analytics_gate
do $g$
begin
  if to_regprocedure('public.analytics_gate(text,date,date,text)') is null then
    alter function public.analytics_report(text,date,date,text)
      rename to analytics_gate;
  end if;
end $g$;

revoke all on function public.analytics_gate(text,date,date,text)
  from public, anon, authenticated;

-- ---- Block 3: the report (check line at the end should say unauthorized)
create or replace function public.analytics_report(
  p_secret text, p_from date default null,
  p_to date default null, p_page text default null)
returns json language plpgsql security definer
set search_path = public as $r$
declare
  v_from date := coalesce(p_from, (now() at time zone 'Asia/Kolkata')::date - 13);
  v_to date := coalesce(p_to, (now() at time zone 'Asia/Kolkata')::date);
  v_out json;
begin
  if p_secret is null or (public.analytics_gate(
       p_secret, v_to, v_to, 'gate-check') ->> 'error') is not null then
    return json_build_object('error', 'unauthorized');
  end if;

  with pv as (
    select * from page_views
    where day between v_from and v_to
      and (p_page is null or page = p_page)
      and left(page, 3) <> '/__'
      and coalesce(host, '') not like 'health.%'
      and coalesce(host, '') not like 'probe.%'
      and coalesce(host, '') <> 'test.local'
  ), ce as (
    select * from click_events
    where day between v_from and v_to
      and (p_page is null or page = p_page)
      and left(page, 3) <> '/__'
  ), src as (
    select case when coalesce(referrer, '') = '' then '(direct)'
           else lower(split_part(split_part(referrer, '://', 2), '/', 1))
           end as source
    from pv
  ), un as (
    select * from unsub_reasons
    where (created_at at time zone 'Asia/Kolkata')::date
          between v_from and v_to
  )
  select json_build_object(
    'from', v_from, 'to', v_to, 'page_filter', p_page,
    'version', '2026-10-20',
    'totals', json_build_object(
      'views', (select count(*) from pv),
      'visitors', (select count(distinct session_id) from pv),
      'clicks', (select count(*) from ce)),
    'daily', (select coalesce(json_agg(row_to_json(t) order by t.day), '[]')
      from (select day::text as day, count(*) as views,
                   count(distinct session_id) as visitors
            from pv group by day) t),
    'top_pages', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select page, count(*) as views,
                   count(distinct session_id) as visitors
            from pv group by page order by count(*) desc limit 40) t),
    'top_clicks', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select target, count(*) as clicks
            from ce group by target order by count(*) desc limit 40) t),
    'top_referrers', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select source as referrer, count(*) as views
            from src where source not like '%mygoldrates%'
            group by source order by count(*) desc limit 20) t),
    'top_hosts', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select coalesce(nullif(host, ''), '(unknown)') as host,
                   count(*) as views
            from pv group by 1 order by count(*) desc limit 10) t),
    'unsubs', json_build_object(
      'total', (select count(*) from un),
      'by_reason', (select coalesce(json_agg(row_to_json(t)), '[]')
        from (select case when reason like 'Other:%' then 'Other'
                     else reason end as reason, count(*) as count
              from un group by 1 order by count(*) desc) t),
      'recent', (select coalesce(json_agg(row_to_json(t)), '[]')
        from (select to_char(created_at at time zone 'Asia/Kolkata',
                             'YYYY-MM-DD HH24:MI') as at, reason
              from un order by created_at desc limit 20) t),
      'subscribers_now', (select count(*) from inquiries
        where email is not null and unsub_token is not null)),
    'lifetime', (select json_build_object(
        'views', count(*), 'visitors', count(distinct session_id),
        'since', min(day)::text)
      from page_views
      where left(page, 3) <> '/__'
        and coalesce(host, '') not like 'health.%'
        and coalesce(host, '') not like 'probe.%'
        and coalesce(host, '') <> 'test.local'),
    'pages_list', (select coalesce(json_agg(page order by page), '[]')
      from (select distinct page from page_views
            where day between v_from and v_to
              and left(page, 3) <> '/__') p)
  ) into v_out;
  return v_out;
end $r$;

revoke all on function public.analytics_report(text,date,date,text) from public;
grant execute on function public.analytics_report(text,date,date,text) to anon;
select public.analytics_report('wrong-token');
