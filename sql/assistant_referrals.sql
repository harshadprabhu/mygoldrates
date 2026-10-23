-- Sona (the site assistant) and referrals, 2026-10-24. New objects only;
-- nothing existing is changed or deleted. Tables are not readable or
-- writable with the public key: the site reaches them only through the
-- security-definer functions below.

-- ---------------------------------------------------------------- Sona
-- What visitors ask. Redacted on the way in (emails, long numbers), kept
-- private: the owner sees it in the analytics page; only answers the owner
-- approves are exported to git (data/assistant_answers.json).
create table if not exists public.bot_questions (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  day date not null default (now() at time zone 'Asia/Kolkata')::date,
  q text not null,
  q_norm text not null,
  intent text,
  answered boolean not null default false,
  helpful boolean,
  page text,
  session_id text
);
create index if not exists bot_questions_day on public.bot_questions (day);
revoke all on public.bot_questions from anon, authenticated;

create table if not exists public.bot_answers (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  q text not null,
  a text not null,
  u text,
  active boolean not null default true
);
revoke all on public.bot_answers from anon, authenticated;

create or replace function public._bot_redact(t text)
returns text language sql immutable as $f$
  select left(regexp_replace(regexp_replace(coalesce(t, ''),
    '[^[:space:]@]+@[^[:space:]@]+', '[email]', 'g'),
    '\+?[0-9][0-9[:space:]-]{6,}[0-9]', '[number]', 'g'), 300)
$f$;

create or replace function public.log_bot_question(
  p_q text, p_intent text, p_answered boolean, p_page text, p_sid text)
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
  insert into bot_questions (q, q_norm, intent, answered, page, session_id)
  values (v, regexp_replace(lower(v), '[^a-z0-9 ]+', '', 'g'), left(p_intent, 30),
          coalesce(p_answered, false), left(p_page, 120), left(p_sid, 64))
  returning id into i;
  return i;
end $f$;

create or replace function public.bot_feedback(p_id bigint, p_sid text, p_helpful boolean)
returns void language sql security definer
set search_path = public as $f$
  update bot_questions set helpful = p_helpful
   where id = p_id and session_id = p_sid and created_at > now() - interval '2 hours'
$f$;

-- Owner actions, behind the analytics secret.
create or replace function public.bot_approve(p_secret text, p_q text, p_a text, p_u text default null)
returns text language plpgsql security definer
set search_path = public as $f$
begin
  if public.analytics_gate(p_secret, current_date, current_date, null)::jsonb ? 'error' then
    return 'unauthorized';
  end if;
  if length(trim(coalesce(p_q, ''))) < 3 or length(trim(coalesce(p_a, ''))) < 3 then
    return 'empty';
  end if;
  insert into bot_answers (q, a, u)
  values (left(trim(p_q), 300), left(trim(p_a), 1500), nullif(left(trim(coalesce(p_u, '')), 300), ''));
  return 'ok';
end $f$;

create or replace function public.bot_unapprove(p_secret text, p_id bigint)
returns text language plpgsql security definer
set search_path = public as $f$
begin
  if public.analytics_gate(p_secret, current_date, current_date, null)::jsonb ? 'error' then
    return 'unauthorized';
  end if;
  update bot_answers set active = false where id = p_id;
  return 'ok';
end $f$;

-- ----------------------------------------------------------- referrals
-- One personal code per subscriber (created by the daily email job), and
-- who joined with whose code. The referrer is emailed once per friend.
create table if not exists public.referral_codes (
  email text primary key,
  code text not null unique,
  created_at timestamptz not null default now()
);
revoke all on public.referral_codes from anon, authenticated;

create table if not exists public.referrals (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  code text not null,
  referrer_email text not null,
  referred_email text not null unique,
  notified_at timestamptz
);
revoke all on public.referrals from anon, authenticated;

create or replace function public.record_referral(p_code text, p_email text)
returns text language plpgsql security definer
set search_path = public as $f$
declare em text := lower(trim(coalesce(p_email, ''))); rc record;
begin
  select * into rc from referral_codes where code = upper(trim(coalesce(p_code, '')));
  if rc is null then return 'code'; end if;
  if lower(rc.email) = em then return 'self'; end if;
  if not exists (select 1 from inquiries i where lower(i.email) = em) then return 'subscribe'; end if;
  -- a referral counts only for someone who joined in the last day
  if not exists (select 1 from inquiries i where lower(i.email) = em
                 and i.created_at > now() - interval '1 day') then return 'old'; end if;
  insert into referrals (code, referrer_email, referred_email)
  values (rc.code, lower(rc.email), em)
  on conflict (referred_email) do nothing;
  return 'ok';
end $f$;

-- ------------------------------------------------------ one-off emails
-- Who received a campaign email, so a re-run never sends it twice.
create table if not exists public.email_campaigns (
  campaign text not null,
  email text not null,
  sent_at timestamptz not null default now(),
  primary key (campaign, email)
);
revoke all on public.email_campaigns from anon, authenticated;

revoke all on function public.log_bot_question(text, text, boolean, text, text) from public;
revoke all on function public.bot_feedback(bigint, text, boolean) from public;
revoke all on function public.bot_approve(text, text, text, text) from public;
revoke all on function public.bot_unapprove(text, bigint) from public;
revoke all on function public.record_referral(text, text) from public;
grant execute on function public.log_bot_question(text, text, boolean, text, text) to anon, authenticated;
grant execute on function public.bot_feedback(bigint, text, boolean) to anon, authenticated;
grant execute on function public.bot_approve(text, text, text, text) to anon, authenticated;
grant execute on function public.bot_unapprove(text, bigint) to anon, authenticated;
grant execute on function public.record_referral(text, text) to anon, authenticated;
