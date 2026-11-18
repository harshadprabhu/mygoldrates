-- Sona feedback, day by day (owner, 18 Nov 2026): "which questions were
-- helpful and which not, every day, so I can push what works and correct
-- what doesn't". Run once in Supabase -> SQL Editor. Safe to re-run.
--
-- 1. Keep the answer Sona gave when a visitor rates it (only rated answers
--    are stored, emails and phone numbers masked, first 600 characters).
alter table public.bot_questions add column if not exists answer text;
alter table public.bot_questions add column if not exists rated_at timestamptz;

create or replace function public.bot_feedback(p_id bigint, p_sid text, p_helpful boolean, p_answer text)
returns void language sql security definer
set search_path = public as $f$
  update bot_questions
     set helpful = p_helpful, rated_at = now(),
         answer = nullif(left(regexp_replace(regexp_replace(coalesce(p_answer, ''),
                    '[^[:space:]@]+@[^[:space:]@]+', '[email]', 'g'),
                    '\+?[0-9][0-9[:space:]-]{6,}[0-9]', '[number]', 'g'), 600), '')
   where id = p_id and session_id = p_sid and created_at > now() - interval '2 hours'
$f$;
revoke all on function public.bot_feedback(bigint, text, boolean, text) from public;
grant execute on function public.bot_feedback(bigint, text, boolean, text) to anon, authenticated;

-- 2. The rated questions in a date range, newest first, for the private
--    analytics page (same secret as the rest of the report).
create or replace function public.bot_feedback_report(p_secret text, p_from date, p_to date)
returns json language plpgsql security definer
set search_path = public as $f$
begin
  if public.analytics_gate(p_secret, p_from, p_to, null)::jsonb ? 'error' then
    return '{"error":"unauthorized"}'::json;
  end if;
  return json_build_object(
    'days', (select coalesce(json_agg(row_to_json(t) order by t.day desc), '[]') from (
      select day, count(*) filter (where helpful) as yes, count(*) filter (where helpful = false) as no,
             count(*) as asked
        from bot_questions b
       where b.day between p_from and p_to and coalesce(b.page, '') not like '/\_\_%'
       group by day) t),
    'rated', (select coalesce(json_agg(row_to_json(t)), '[]') from (
      select day, to_char(coalesce(rated_at, created_at) at time zone 'Asia/Kolkata', 'HH24:MI') as at,
             q, intent, helpful, answered, page, answer
        from bot_questions b
       where b.day between p_from and p_to and b.helpful is not null
         and coalesce(b.page, '') not like '/\_\_%'
       order by b.day desc, b.id desc limit 500) t));
end $f$;
revoke all on function public.bot_feedback_report(text, date, date) from public;
grant execute on function public.bot_feedback_report(text, date, date) to anon, authenticated;

-- check: should return {"error":"unauthorized"}
select public.bot_feedback_report('wrong', current_date, current_date);
