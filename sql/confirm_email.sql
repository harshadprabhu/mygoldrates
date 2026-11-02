-- Email confirmation for subscribers (2026-11-02, approved by the owner).
--
-- Why: anyone could type any address into a signup box and that address
-- started getting our emails. Now a new address gets ONE "confirm your email"
-- message and nothing else until the link in it is clicked. A Google sign-in
-- is confirmed by checking Google's signed token on the server instead.
--
-- How the mail goes out: a trigger on inquiries asks the Jewellers Digest
-- Worker (which holds the Brevo key) to send it, through pg_net. Every way
-- of signing up writes this table, so every way is covered. The Worker sends
-- at most one confirmation per address per 24 hours.
--
-- Senders (send_alerts.py, promo_email.py) skip rows without confirmed_at.

create extension if not exists pg_net with schema extensions;

alter table public.inquiries add column if not exists confirmed_at    timestamptz;
alter table public.inquiries add column if not exists confirm_sent_at timestamptz;
alter table public.inquiries add column if not exists confirm_token   uuid default gen_random_uuid();
update public.inquiries set confirm_token = gen_random_uuid() where confirm_token is null;
create unique index if not exists inquiries_confirm_token_uidx on public.inquiries (confirm_token);

-- Existing subscribers have been getting mail for weeks: keep them, except
-- the one address the owner reported was added without anyone signing up.
update public.inquiries set confirmed_at = coalesce(created_at, now())
 where confirmed_at is null
   and lower(email) <> 'harshad.prabhu@adityabirla.com';
-- ...and that one gets no confirmation email either (it was never asked for).
update public.inquiries set confirm_sent_at = now()
 where lower(email) = 'harshad.prabhu@adityabirla.com';

-- The confirm page calls this with the token from the link.
create or replace function public.confirm_subscriber(p_token uuid)
returns text language plpgsql security definer set search_path = public as $f$
begin
  update inquiries set confirmed_at = coalesce(confirmed_at, now()), updated_at = now()
   where confirm_token = p_token;
  if not found then return 'bad'; end if;
  return 'ok';
end $f$;
revoke all on function public.confirm_subscriber(uuid) from public;
grant execute on function public.confirm_subscriber(uuid) to anon, authenticated;

-- Worker only (service role): may a confirmation go to this address now?
-- Returns the token and name and stamps the send time, or nothing.
create or replace function public.confirm_request(p_email text)
returns table (token uuid, name text) language plpgsql security definer
set search_path = public as $f$
begin
  return query
  with u as (
    update inquiries i set confirm_sent_at = now()
     where lower(i.email) = lower(trim(p_email))
       and i.confirmed_at is null
       and (i.confirm_sent_at is null or i.confirm_sent_at < now() - interval '24 hours')
    returning i.confirm_token as t, i.name as n)
  select u.t, u.n from u;
end $f$;
revoke all on function public.confirm_request(text) from public, anon, authenticated;
grant execute on function public.confirm_request(text) to service_role;

-- Worker only: Google's token for this address checked out.
create or replace function public.confirm_google(p_email text)
returns text language plpgsql security definer set search_path = public as $f$
begin
  update inquiries set confirmed_at = coalesce(confirmed_at, now()), updated_at = now()
   where lower(email) = lower(trim(p_email));
  if not found then return 'missing'; end if;
  return 'ok';
end $f$;
revoke all on function public.confirm_google(text) from public, anon, authenticated;
grant execute on function public.confirm_google(text) to service_role;

-- New or re-subscribing unconfirmed address -> ask the Worker to send the
-- confirmation. Google sign-ups are left to the page, which sends Google's
-- token to the Worker (and falls back to this email if the token fails).
create or replace function public.inquiries_confirm_mail()
returns trigger language plpgsql security definer set search_path = public as $f$
begin
  perform net.http_post(
    url     := 'https://mygoldrates-jd-api.harshads-priority.workers.dev/sub/confirm',
    body    := jsonb_build_object('email', new.email),
    headers := '{"Content-Type": "application/json"}'::jsonb);
  return new;
end $f$;

drop trigger if exists inquiries_confirm_mail on public.inquiries;
create trigger inquiries_confirm_mail
  after insert or update on public.inquiries
  for each row
  when (new.confirmed_at is null
        and new.email is not null
        and coalesce(new.signup_method, '') <> 'google'
        and (new.confirm_sent_at is null or new.confirm_sent_at < now() - interval '24 hours'))
  execute function public.inquiries_confirm_mail();
