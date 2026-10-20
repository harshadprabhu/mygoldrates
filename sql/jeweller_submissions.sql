-- Jewellers who send their own daily rate (2026-10-20).
--
-- Two steps, both through security-definer functions; the tables are not
-- readable or writable by the public key:
--   1. A jeweller applies on /list-your-jewellery: details plus today's
--      rate go into jeweller_applications as 'pending' for the owner to
--      review. Nothing is published from an application.
--   2. Once approved, the jeweller gets a personal code (only its hash is
--      stored) and posts each day's rate with it into jeweller_daily_rates.
--      collect.py reads today's row for brands whose rate_url is
--      'submitted:<slug>' and puts it through the same 4% market check as
--      every other rate.
-- New objects only; nothing existing is changed.

create table if not exists public.jeweller_applications (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  jeweller text not null,
  city text not null,
  state text not null,
  website text,
  contact_name text,
  phone text,
  email text,
  instagram text,
  rate_24k numeric,
  rate_22k numeric,
  rate_18k numeric,
  includes_gst boolean not null default false,
  note text,
  status text not null default 'pending'
);
revoke all on public.jeweller_applications from anon, authenticated;

create table if not exists public.jeweller_codes (
  slug text primary key,
  code_hash text not null,
  created_at timestamptz not null default now()
);
revoke all on public.jeweller_codes from anon, authenticated;

create table if not exists public.jeweller_daily_rates (
  id bigint generated always as identity primary key,
  slug text not null,
  rate_date date not null default (now() at time zone 'Asia/Kolkata')::date,
  rate_24k numeric,
  rate_22k numeric,
  rate_18k numeric,
  includes_gst boolean not null default false,
  submitted_at timestamptz not null default now(),
  unique (slug, rate_date)
);
revoke all on public.jeweller_daily_rates from anon, authenticated;

-- A per-gram rate has to look like one: between Rs 3,000 and Rs 30,000.
create or replace function public._rate_ok(v numeric)
returns boolean language sql immutable as $f$
  select v is null or (v between 3000 and 30000)
$f$;

create or replace function public.apply_as_jeweller(
  jeweller text, city text, state text, website text, contact_name text,
  phone text, email text, instagram text,
  r24 numeric, r22 numeric, r18 numeric, gst boolean, note text)
returns text language plpgsql security definer
set search_path = public as $f$
begin
  if coalesce(trim(jeweller), '') = '' or coalesce(trim(city), '') = ''
     or coalesce(trim(state), '') = '' then
    return 'missing';
  end if;
  if coalesce(trim(phone), '') = '' and coalesce(trim(email), '') = '' then
    return 'contact';
  end if;
  if r24 is null and r22 is null and r18 is null then
    return 'rate';
  end if;
  if not (_rate_ok(r24) and _rate_ok(r22) and _rate_ok(r18)) then
    return 'range';
  end if;
  -- at most 5 applications a day from one phone or email
  if (select count(*) from jeweller_applications a
      where a.created_at > now() - interval '1 day'
        and ((coalesce(apply_as_jeweller.phone, '') <> ''
              and a.phone = apply_as_jeweller.phone)
          or (coalesce(apply_as_jeweller.email, '') <> ''
              and a.email = apply_as_jeweller.email))) >= 5 then
    return 'limit';
  end if;
  insert into jeweller_applications(jeweller, city, state, website,
      contact_name, phone, email, instagram, rate_24k, rate_22k, rate_18k,
      includes_gst, note)
  values (left(trim(jeweller), 120), left(trim(city), 80), left(trim(state), 80),
      left(website, 200), left(contact_name, 120), left(phone, 20),
      left(email, 160), left(instagram, 120), r24, r22, r18,
      coalesce(gst, false), left(note, 500));
  return 'ok';
end $f$;

create or replace function public.submit_daily_rate(
  code text, r24 numeric, r22 numeric, r18 numeric, gst boolean)
returns text language plpgsql security definer
set search_path = public, extensions as $f$
declare s text;
begin
  select c.slug into s from jeweller_codes c
   where c.code_hash = encode(extensions.digest(coalesce(code, ''), 'sha256'), 'hex');
  if s is null then
    return 'code';
  end if;
  if r24 is null and r22 is null and r18 is null then
    return 'rate';
  end if;
  if not (_rate_ok(r24) and _rate_ok(r22) and _rate_ok(r18)) then
    return 'range';
  end if;
  insert into jeweller_daily_rates(slug, rate_24k, rate_22k, rate_18k, includes_gst)
  values (s, r24, r22, r18, coalesce(gst, false))
  on conflict (slug, rate_date) do update
     set rate_24k = excluded.rate_24k, rate_22k = excluded.rate_22k,
         rate_18k = excluded.rate_18k, includes_gst = excluded.includes_gst,
         submitted_at = now();
  return 'ok';
end $f$;

grant execute on function public.apply_as_jeweller(text, text, text, text, text,
  text, text, text, numeric, numeric, numeric, boolean, text) to anon, authenticated;
grant execute on function public.submit_daily_rate(text, numeric, numeric,
  numeric, boolean) to anon, authenticated;

-- Approving an application (run by the owner, with values filled in):
--   insert into brands (slug, name, domain, rate_url, includes_gst, active)
--   values ('<slug>', '<name>', '<website or empty>', 'submitted:<slug>', false, true);
--   insert into jeweller_codes (slug, code_hash)
--   values ('<slug>', encode(extensions.digest('<code you send them>', 'sha256'), 'hex'));
--   update jeweller_applications set status = 'approved' where id = <id>;
