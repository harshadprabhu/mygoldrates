-- Private analytics, version 2 (2026-10-23): filters and comparisons.
--
-- New objects plus one new nullable column; nothing existing is changed or
-- deleted. analytics_report() stays as it is; analytics_report_v2() reuses
-- it (same secret check) for the subscriber, jeweller and all-time cards
-- and adds:
--   filters   p_filters: {"page", "page_group", "source", "host", "device"}
--   compare   totals for the previous period of the same length
--   series    daily views/visitors, views by IST hour
--   breakdown page groups, traffic-source groups, raw referrers, hosts,
--             devices, landing pages (first page of each visit), top pages,
--             top clicks
--   signups   new subscribers in the range, by sign-up method
--   funnel    sign-up popup and form events (shown, closed, subscribed,
--             price alert, mobile added) - added 2026-10-24
-- Clicks have no referrer or device, so a source/device filter keeps the
-- clicks made in the visits that match it.

-- Device type, sent by the page-view beacon from 2026-10-23 on.
alter table public.page_views add column if not exists device text;
do $c$ begin
  if not exists (select 1 from pg_constraint where conname = 'page_views_device_chk') then
    alter table public.page_views add constraint page_views_device_chk
      check (device is null or device in ('mobile', 'tablet', 'desktop'));
  end if;
end $c$;

-- One spelling per page: "/x.html", "/x/" and "/x" are the same page.
create or replace function public._pv_page(p text)
returns text language sql immutable as $f$
  select case when coalesce(p, '') in ('', '/', '/index', '/index.html') then '/'
              else regexp_replace(regexp_replace(p, '\.html$', ''), '/+$', '') end
$f$;

create or replace function public._pv_page_group(p text)
returns text language sql immutable as $f$
  select case
    when p = '/' then 'Home'
    when p ~ '^/gold-rate-today-in-' then 'City & state pages'
    when p ~ '-gold-rate-today$' or p = '/gold-rate-by-jeweller' then 'Jeweller pages'
    when p = '/gold-rate-near-me' then 'Near me'
    when p ~ 'calculator' then 'Calculators'
    when p ~ '^/learn/' or p in ('/methodology', '/making-charges-comparison')
         or p ~ '^/dhanteras' then 'Guides & reports'
    when p ~ '^/news' or p = '/gold-market-today' then 'News & market brief'
    when p ~ '^/gold-rate-history' then 'Rate history'
    when p ~ '^/(inquiry|unsubscribe|list-your-jewellery|jewellers-digest|jd-today)' then 'Sign-up & members'
    else 'Other pages' end
$f$;

create or replace function public._pv_ref_host(r text)
returns text language sql immutable as $f$
  select case when coalesce(r, '') = '' then ''
              else lower(split_part(split_part(r, '://', 2), '/', 1)) end
$f$;

create or replace function public._pv_source(r text)
returns text language sql immutable as $f$
  select case
    when h = '' then 'Direct'
    when h ~ 'mygoldrates' then 'Within the site'
    when h ~ '(^|\.)google\.' then 'Google'
    when h ~ '(^|\.)bing\.com$' then 'Bing'
    when h ~ '(duckduckgo|yahoo|yandex|ecosia|search\.brave|qwant|baidu)' then 'Other search'
    when h ~ '(chatgpt|openai|perplexity|claude\.ai|gemini|copilot|you\.com)' then 'AI assistants'
    when h ~ '(instagram|facebook|(^|\.)fb\.|(^|\.)t\.co$|twitter|(^|\.)x\.com$|linkedin|whatsapp|wa\.me|youtube|reddit|telegram|pinterest|threads)' then 'Social'
    when h ~ 'pages\.dev$' then 'Site preview copies'
    else 'Other websites' end
  from (select public._pv_ref_host(r) as h) x
$f$;

create or replace function public.analytics_report_v2(
  p_secret text, p_from date default null, p_to date default null,
  p_filters jsonb default '{}'::jsonb)
returns json language plpgsql security definer
set search_path = public as $r$
declare
  v_from date := coalesce(p_from, (now() at time zone 'Asia/Kolkata')::date - 13);
  v_to   date := coalesce(p_to, (now() at time zone 'Asia/Kolkata')::date);
  v_len  int;
  f_page text := nullif(p_filters ->> 'page', '');
  f_grp  text := nullif(p_filters ->> 'page_group', '');
  f_src  text := nullif(p_filters ->> 'source', '');
  f_host text := nullif(p_filters ->> 'host', '');
  f_dev  text := nullif(p_filters ->> 'device', '');
  v_base jsonb;
  v_new  json;
begin
  v_base := public.analytics_report(p_secret, v_from, v_to, null)::jsonb;
  if v_base ? 'error' then
    return v_base::json;
  end if;
  v_len := v_to - v_from + 1;

  with pv_all as (
    select p.day, p.created_at, p.session_id,
           public._pv_page(p.page) as page,
           public._pv_page_group(public._pv_page(p.page)) as page_group,
           public._pv_source(p.referrer) as source,
           public._pv_ref_host(p.referrer) as ref_host,
           coalesce(nullif(p.host, ''), '(unknown)') as host,
           coalesce(p.device, '(not recorded)') as device
    from page_views p
    where p.day between v_from - v_len and v_to
      and left(coalesce(p.page, ''), 3) <> '/__'
      and coalesce(p.host, '') not like 'health.%'
      and coalesce(p.host, '') not like 'probe.%'
      and coalesce(p.host, '') <> 'test.local'
  ), pvf as (
    select * from pv_all
    where (f_page is null or page = f_page)
      and (f_grp  is null or page_group = f_grp)
      and (f_src  is null or source = f_src)
      and (f_host is null or host = f_host)
      and (f_dev  is null or device = f_dev)
  ), cur as (select * from pvf where day between v_from and v_to),
     prev as (select * from pvf where day < v_from),
  ce_all as (
    select c.day, c.session_id, public._pv_page(c.page) as page, c.target
    from click_events c
    where c.day between v_from - v_len and v_to
      and left(coalesce(c.page, ''), 3) <> '/__'
  ), cef as (
    select * from ce_all c
    where (f_page is null or c.page = f_page)
      and (f_grp is null or public._pv_page_group(c.page) = f_grp)
      and ((f_src is null and f_host is null and f_dev is null)
           or exists (select 1 from pvf v where v.session_id = c.session_id and v.day = c.day))
  ), sess as (
    select session_id, count(*) as n from cur group by session_id
  ), land as (
    select distinct on (session_id, day) session_id, day, page
    from cur order by session_id, day, created_at
  ), subs as (
    select (created_at at time zone 'Asia/Kolkata')::date as day,
           coalesce(nullif(signup_method, ''), 'form') as method
    from inquiries
    where email is not null
      and (created_at at time zone 'Asia/Kolkata')::date between v_from - v_len and v_to
  )
  select json_build_object(
    'version', 'v2-2026-10-24b',
    'filters', p_filters,
    'totals', json_build_object(
      'views', (select count(*) from cur),
      'visitors', (select count(distinct session_id) from cur),
      'clicks', (select count(*) from cef where day between v_from and v_to),
      'single_page_visits', (select count(*) from sess where n = 1),
      'signups', (select count(*) from subs where day between v_from and v_to)),
    'prev', json_build_object(
      'from', v_from - v_len, 'to', v_from - 1,
      'views', (select count(*) from prev),
      'visitors', (select count(distinct session_id) from prev),
      'clicks', (select count(*) from cef where day < v_from),
      'signups', (select count(*) from subs where day < v_from)),
    'daily', (select coalesce(json_agg(row_to_json(t) order by t.day), '[]')
      from (select d::date::text as day,
                   (select count(*) from cur where cur.day = d::date) as views,
                   (select count(distinct session_id) from cur where cur.day = d::date) as visitors,
                   (select count(*) from subs where subs.day = d::date) as signups
            from generate_series(v_from, v_to, interval '1 day') d) t),
    'hourly', (select coalesce(json_agg(row_to_json(t) order by t.hour), '[]')
      from (select h as hour,
                   (select count(*) from cur
                     where extract(hour from cur.created_at at time zone 'Asia/Kolkata') = h) as views
            from generate_series(0, 23) h) t),
    'page_groups', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select page_group as name, count(*) as views,
                   count(distinct session_id) as visitors
            from cur group by 1 order by 2 desc) t),
    'sources', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select source as name, count(*) as views,
                   count(distinct session_id) as visitors
            from cur group by 1 order by 2 desc) t),
    'referrers', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select ref_host as name, source, count(*) as views
            from cur where ref_host <> '' and source <> 'Within the site'
            group by 1, 2 order by 3 desc limit 30) t),
    'hosts', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select host as name, count(*) as views from cur
            group by 1 order by 2 desc limit 10) t),
    'devices', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select device as name, count(*) as views,
                   count(distinct session_id) as visitors
            from cur group by 1 order by 2 desc) t),
    'top_pages', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select page, page_group, count(*) as views,
                   count(distinct session_id) as visitors
            from cur group by 1, 2 order by 3 desc limit 100) t),
    'landing_pages', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select page, count(*) as visits from land
            group by 1 order by 2 desc limit 30) t),
    'top_clicks', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select target, count(*) as clicks from cef
            where day between v_from and v_to and target not like 'funnel:%'
            group by 1 order by 2 desc limit 80) t),
    'funnel', (select coalesce(json_object_agg(target, n), '{}')
      from (select target, count(*) as n from cef
            where day between v_from and v_to
              and (target like 'funnel:%' or target in
                   ('spClose', 'spSureYes', 'spSureNo', 'spHave'))
            group by 1) t),
    'price_alerts', (select count(*) from price_alerts a
      where (a.created_at at time zone 'Asia/Kolkata')::date between v_from and v_to),
    'bot', json_build_object(
      'asked', (select count(*) from bot_questions b where b.day between v_from and v_to
                and coalesce(b.page, '') not like '/\_\_%'),
      'answered', (select count(*) from bot_questions b where b.day between v_from and v_to
                   and b.answered and coalesce(b.page, '') not like '/\_\_%'),
      'helpful_yes', (select count(*) from bot_questions b where b.day between v_from and v_to and b.helpful),
      'helpful_no', (select count(*) from bot_questions b where b.day between v_from and v_to and b.helpful = false),
      'intents', (select coalesce(json_agg(row_to_json(t)), '[]') from (
                  select coalesce(intent, '?') as name, count(*) as n from bot_questions b
                  where b.day between v_from and v_to and coalesce(b.page, '') not like '/\_\_%'
                  group by 1 order by 2 desc) t),
      -- what Sona could not answer, or answered and got a thumbs-down
      'unanswered', (select coalesce(json_agg(row_to_json(t)), '[]') from (
                  select min(q) as q, count(*) as n, bool_or(helpful = false) as disliked,
                         max(created_at)::date as last
                  from bot_questions b
                  where b.day between v_from and v_to and coalesce(b.page, '') not like '/\_\_%'
                    and (not b.answered or b.helpful = false)
                  group by q_norm order by 2 desc, 4 desc limit 40) t),
      'approved', (select coalesce(json_agg(row_to_json(t)), '[]') from (
                  select id, q, a, u, created_at::date as d from bot_answers
                  where active order by id desc limit 100) t)),
    'referrals', json_build_object(
      'joined', (select count(*) from referrals r
                 where (r.created_at at time zone 'Asia/Kolkata')::date between v_from and v_to),
      'notified', (select count(*) from referrals r where r.notified_at is not null
                 and (r.created_at at time zone 'Asia/Kolkata')::date between v_from and v_to),
      'top', (select coalesce(json_agg(row_to_json(t)), '[]') from (
                 select referrer_email as who, count(*) as n from referrals r
                 where (r.created_at at time zone 'Asia/Kolkata')::date between v_from and v_to
                 group by 1 order by 2 desc limit 10) t)),
    'signup_methods', (select coalesce(json_agg(row_to_json(t)), '[]')
      from (select method as name, count(*) as signups from subs
            where day between v_from and v_to group by 1 order by 2 desc) t),
    'pages_list', (select coalesce(json_agg(page order by page), '[]')
      from (select distinct page from pv_all where day between v_from and v_to) p),
    'hosts_list', (select coalesce(json_agg(host order by host), '[]')
      from (select distinct host from pv_all where day between v_from and v_to) p)
  ) into v_new;

  return (v_base - 'top_pages' - 'top_clicks' - 'top_referrers' - 'top_hosts'
                 - 'daily' - 'totals' - 'pages_list' || v_new::jsonb)::json;
end $r$;

revoke all on function public.analytics_report_v2(text, date, date, jsonb) from public;
grant execute on function public.analytics_report_v2(text, date, date, jsonb) to anon;
select public.analytics_report_v2('wrong-token');
