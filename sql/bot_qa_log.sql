-- Sona: the FULL questions-and-answers log for the private analytics page
-- (owner, 24 Nov 2026). Until now the answer was kept only when a visitor
-- rated it, and the report returned only rated questions - so the log looked
-- almost empty (447 asked, ~21 rated). This keeps the answer Sona gave with
-- EVERY question, and adds a report that returns them all. Run once in
-- Supabase -> SQL Editor. Safe to re-run; new objects / in-place updates only.

-- The answer column (also added by bot_feedback_report.sql; harmless to repeat).
alter table public.bot_questions add column if not exists answer text;

-- 1) log_bot_question now stores the answer too, redacted (emails / phone
--    numbers masked, first 600 chars). The old 5-argument version is dropped
--    and replaced by a 6-argument one whose p_answer defaults to null, so any
--    old cached site code that still calls it with 5 arguments keeps working.
drop function if exists public.log_bot_question(text, text, boolean, text, text);
create or replace function public.log_bot_question(
  p_q text, p_intent text, p_answered boolean, p_page text, p_sid text,
  p_answer text default null)
returns bigint language plpgsql security definer
set search_path = public as $f$
declare v text := trim(public._bot_redact(p_q)); i bigint;
begin
  if length(v) < 2 then return null; end if;
  -- at most 60 questions an hour from one visitor
  if coalesce(p_sid, '') <> '' and (select count(*) from bot_questions b
      where b.session_id = p_sid and b.created_at > now() - interval '1 hour') >= 60 then
    return null;
  end if;
  insert into bot_questions (q, q_norm, intent, answered, page, session_id, answer)
  values (v, regexp_replace(lower(v), '[^a-z0-9 ]+', '', 'g'), left(p_intent, 30),
          coalesce(p_answered, false), left(p_page, 120), left(p_sid, 64),
          nullif(left(public._bot_redact(p_answer), 600), ''))
  returning id into i;
  return i;
end $f$;
revoke all on function public.log_bot_question(text, text, boolean, text, text, text) from public;
grant execute on function public.log_bot_question(text, text, boolean, text, text, text) to anon, authenticated;

-- 2) The full Q&A log for a date range: every question with the answer Sona
--    gave, newest first, behind the same analytics secret as the rest of the
--    dashboard. Probe pages (/__...) are excluded, like the other reports.
create or replace function public.bot_qa_log(p_secret text, p_from date, p_to date)
returns json language plpgsql security definer
set search_path = public as $f$
begin
  if public.analytics_gate(p_secret, p_from, p_to, null)::jsonb ? 'error' then
    return '{"error":"unauthorized"}'::json;
  end if;
  return coalesce((select json_agg(row_to_json(t)) from (
    select to_char(created_at at time zone 'Asia/Kolkata', 'DD Mon HH24:MI') as at,
           day, q, intent, answered, helpful, answer, page
      from bot_questions b
     where b.day between p_from and p_to
       and coalesce(b.page, '') not like '/\_\_%'
     order by b.id desc
     limit 1000) t), '[]'::json);
end $f$;
revoke all on function public.bot_qa_log(text, date, date) from public;
grant execute on function public.bot_qa_log(text, date, date) to anon, authenticated;

-- check: should return {"error":"unauthorized"}
select public.bot_qa_log('wrong', current_date, current_date);
