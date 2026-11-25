-- Customer Trends report (owner, 25 Nov 2026). One aggregation RPC behind the
-- same analytics secret as the rest of the dashboard, feeding the private
-- /trends page (Google-sign-in gated to the owner). It summarises what
-- subscribers tell us about what they want to buy (buy_for / buy_when), the
-- categories, brands, cities and karats they care about (the `interest` jsonb
-- that Sona accumulates per logged-in user), where they are (state), and what
-- the whole audience asks Sona about (bot_questions topics) - with a weekly
-- trend line. Read-only; aggregates only. Run once in Supabase -> SQL Editor.
-- Safe to re-run: in-place function replacement only, no data touched.

create or replace function public.customer_trends(p_secret text, p_from date, p_to date)
returns json language plpgsql security definer
set search_path = public as $f$
declare r json;
begin
  if public.analytics_gate(p_secret, p_from, p_to, null)::jsonb ? 'error' then
    return '{"error":"unauthorized"}'::json;
  end if;

  select json_build_object(
    'range', json_build_object('from', p_from, 'to', p_to),

    -- Headline counts
    'totals', json_build_object(
      'subscribers',           (select count(*) from inquiries
                                  where created_at::date between p_from and p_to),
      'with_intent',           (select count(*) from inquiries
                                  where intent_at is not null
                                    and intent_at::date between p_from and p_to),
      'questions',             (select count(*) from bot_questions
                                  where day between p_from and p_to
                                    and coalesce(page,'') not like '/\_\_%')
    ),

    -- Why are they buying: wedding / festival / investment / gift / self
    'buy_for', coalesce((select json_object_agg(buy_for, n) from (
      select buy_for, count(*) n from inquiries
       where buy_for is not null and intent_at::date between p_from and p_to
       group by buy_for order by n desc) t), '{}'::json),

    -- When: this_month / 3_months / 6_months / later ...
    'buy_when', coalesce((select json_object_agg(buy_when, n) from (
      select buy_when, count(*) n from inquiries
       where buy_when is not null and intent_at::date between p_from and p_to
       group by buy_when order by n desc) t), '{}'::json),

    -- Categories people care about (interest keys: cat_Ring, cat_Necklace ...)
    'categories', coalesce((select json_object_agg(cat, n) from (
      select substring(k from 5) cat, count(*) n
        from inquiries, jsonb_object_keys(interest) k
       where interest is not null and k like 'cat\_%'
         and intent_at::date between p_from and p_to
       group by k order by n desc limit 15) t), '{}'::json),

    -- What they ask Sona about (interest keys: ask_price, ask_making ...)
    'topics_asked', coalesce((select json_object_agg(topic, n) from (
      select substring(k from 5) topic, count(*) n
        from inquiries, jsonb_object_keys(interest) k
       where interest is not null and k like 'ask\_%'
         and intent_at::date between p_from and p_to
       group by k order by n desc limit 15) t), '{}'::json),

    -- Brands they looked up (interest->>'brand')
    'top_brands', coalesce((select json_object_agg(b, n) from (
      select interest->>'brand' b, count(*) n from inquiries
       where interest ? 'brand' and intent_at::date between p_from and p_to
       group by 1 order by n desc limit 12) t), '{}'::json),

    -- Karat preference (interest->>'karat')
    'karat', coalesce((select json_object_agg(k, n) from (
      select interest->>'karat' k, count(*) n from inquiries
       where interest ? 'karat' and intent_at::date between p_from and p_to
       group by 1 order by n desc) t), '{}'::json),

    -- Geography: where subscribers are, by state (signup-time)
    'by_state', coalesce((select json_agg(row_to_json(t)) from (
      select state, count(*) n from inquiries
       where state is not null and state <> ''
         and created_at::date between p_from and p_to
       group by state order by n desc limit 20) t), '[]'::json),

    -- Cities people ask Sona to compare (interest->>'city')
    'by_city', coalesce((select json_agg(row_to_json(t)) from (
      select interest->>'city' city, count(*) n from inquiries
       where interest ? 'city' and intent_at::date between p_from and p_to
       group by 1 order by n desc limit 15) t), '[]'::json),

    -- What the WHOLE audience asks Sona (anonymous, from bot_questions)
    'sona_intents', coalesce((select json_object_agg(intent, n) from (
      select intent, count(*) n from bot_questions
       where intent is not null and intent <> ''
         and day between p_from and p_to
         and coalesce(page,'') not like '/\_\_%'
       group by intent order by n desc limit 20) t), '{}'::json),

    -- Weekly trend: stated-intent subscribers per ISO week, split by buy_for
    'weekly', coalesce((select json_agg(row_to_json(t)) from (
      select to_char(date_trunc('week', intent_at), 'YYYY-MM-DD') as week,
             coalesce(buy_for, 'unspecified') as buy_for,
             count(*) n
        from inquiries
       where intent_at is not null and intent_at::date between p_from and p_to
       group by 1, 2 order by 1) t), '[]'::json),

    -- Weekly total questions asked (whole audience) - adoption curve
    'questions_weekly', coalesce((select json_agg(row_to_json(t)) from (
      select to_char(date_trunc('week', day::timestamp), 'YYYY-MM-DD') as week,
             count(*) n
        from bot_questions
       where day between p_from and p_to
         and coalesce(page,'') not like '/\_\_%'
       group by 1 order by 1) t), '[]'::json)
  ) into r;

  return r;
end $f$;

revoke all on function public.customer_trends(text, date, date) from public;
grant execute on function public.customer_trends(text, date, date) to anon, authenticated;

-- check: should return {"error":"unauthorized"}
select public.customer_trends('wrong', current_date - 30, current_date);
