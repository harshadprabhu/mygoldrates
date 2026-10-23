-- Price-drop alerts (2026-10-24).
--
-- A subscriber asks to be emailed once when today's lowest 22K (or 24K /
-- 18K) rate among the national jewellers falls to or below a price they
-- choose. send_alerts.py checks after every collect and sends one email,
-- then marks the alert used. New objects only; nothing existing changes.
-- The table is not readable or writable with the public key; the site sets
-- an alert only through set_price_alert(), and only for an email that is
-- already subscribed.

create table if not exists public.price_alerts (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  email text not null,
  karat text not null default '22K' check (karat in ('24K', '22K', '18K')),
  target numeric not null check (target between 3000 and 30000),
  source text,
  active boolean not null default true,
  fired_at timestamptz,
  fired_rate numeric
);
-- One live alert per person and purity; a new one replaces the old.
create unique index if not exists price_alerts_one_active
  on public.price_alerts (lower(email), karat) where active;
revoke all on public.price_alerts from anon, authenticated;

create or replace function public.set_price_alert(
  p_email text, p_target numeric, p_karat text default '22K',
  p_source text default null)
returns text language plpgsql security definer
set search_path = public as $f$
declare em text := lower(nullif(trim(p_email), ''));
begin
  if em is null or em !~ '^[^\s@]+@[^\s@]+\.[^\s@]+$' then
    return 'email';
  end if;
  if coalesce(p_karat, '') not in ('24K', '22K', '18K') then
    return 'karat';
  end if;
  if p_target is null or p_target not between 3000 and 30000 then
    return 'range';
  end if;
  if not exists (select 1 from inquiries i where lower(i.email) = em) then
    return 'subscribe';
  end if;
  if (select count(*) from price_alerts a
      where lower(a.email) = em and a.created_at > now() - interval '1 day') >= 20 then
    return 'limit';
  end if;
  update price_alerts a set active = false
   where lower(a.email) = em and a.karat = p_karat and a.active;
  insert into price_alerts (email, karat, target, source)
  values (em, p_karat, round(p_target), left(p_source, 40));
  return 'ok';
end $f$;

revoke all on function public.set_price_alert(text, numeric, text, text) from public;
grant execute on function public.set_price_alert(text, numeric, text, text) to anon, authenticated;
