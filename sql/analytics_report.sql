-- Secret-gated analytics read function for the private dashboard page.
--
-- WHY a secret: page_views / click_events are insert-only to the public (anon)
-- key by RLS, so the browser can log hits but cannot read them back. The private
-- report page needs to READ aggregates. This SECURITY DEFINER function bypasses
-- RLS to compute aggregates, but ONLY returns them when called with the correct
-- secret token — so possessing the public anon key alone is not enough.
--
-- The real token lives in the GitHub secret ANALYTICS_TOKEN (injected into the
-- dashboard page at build time) and in this function body. Do NOT commit the
-- real token here — replace __ANALYTICS_TOKEN__ below with the real value only
-- when pasting into the Supabase SQL Editor (the filled version is never stored
-- in git). Returns only aggregate counts — never a raw row, never any PII.

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
  -- gate: wrong/missing secret returns an error object, no data
  if p_secret is distinct from '__ANALYTICS_TOKEN__' then
    return json_build_object('error', 'unauthorized');
  end if;

  select json_build_object(
    'from', v_from,
    'to',   v_to,
    'page_filter', p_page,
    'totals', (
      select json_build_object(
        'views',    count(*),
        'visitors', count(distinct session_id),
        'clicks',   (select count(*) from click_events c
                      where c.day between v_from and v_to
                        and (p_page is null or c.page = p_page))
      )
      from page_views pv
      where pv.day between v_from and v_to
        and (p_page is null or pv.page = p_page)
    ),
    'daily', (
      select coalesce(json_agg(row_to_json(t) order by t.day), '[]'::json) from (
        select day::text as day, count(*) as views,
               count(distinct session_id) as visitors
        from page_views
        where day between v_from and v_to
          and (p_page is null or page = p_page)
        group by day
      ) t
    ),
    'top_pages', (
      select coalesce(json_agg(row_to_json(t)), '[]'::json) from (
        select page, count(*) as views, count(distinct session_id) as visitors
        from page_views
        where day between v_from and v_to
          and (p_page is null or page = p_page)
        group by page order by count(*) desc limit 40
      ) t
    ),
    'top_clicks', (
      select coalesce(json_agg(row_to_json(t)), '[]'::json) from (
        select target, count(*) as clicks
        from click_events
        where day between v_from and v_to
          and (p_page is null or page = p_page)
        group by target order by count(*) desc limit 40
      ) t
    ),
    'top_referrers', (
      select coalesce(json_agg(row_to_json(t)), '[]'::json) from (
        select coalesce(nullif(referrer, ''), '(direct)') as referrer,
               count(*) as views
        from page_views
        where day between v_from and v_to
          and (p_page is null or page = p_page)
        group by 1 order by count(*) desc limit 20
      ) t
    ),
    -- Verifies the www->apex redirect (cf-redirect.yml): www hits should
    -- trend to ~0 once it's live and being respected by browsers/crawlers.
    'top_hosts', (
      select coalesce(json_agg(row_to_json(t)), '[]'::json) from (
        select coalesce(nullif(host, ''), '(unknown)') as host,
               count(*) as views
        from page_views
        where day between v_from and v_to
          and (p_page is null or page = p_page)
        group by 1 order by count(*) desc limit 10
      ) t
    ),
    'pages_list', (
      select coalesce(json_agg(page order by page), '[]'::json) from (
        select distinct page from page_views where day between v_from and v_to
      ) p
    )
  ) into v_out;

  return v_out;
end $$;

revoke all on function public.analytics_report(text,date,date,text) from public;
grant execute on function public.analytics_report(text,date,date,text) to anon;
