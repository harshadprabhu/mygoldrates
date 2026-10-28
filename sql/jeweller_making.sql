-- Jewellers send their own making charges (2026-10-28).
--
-- Many jewellers publish no making charge online, so the comparison cannot
-- measure one. A listed jeweller (one with a personal code from
-- sql/jeweller_submissions.sql) can send its typical making charge per
-- category, as a % of the gold value on plain gold, before offers. The site
-- shows it marked "supplied by the jeweller"; a category we measure from real
-- products keeps the measured figure. Like the daily rate, it goes through a
-- security-definer function that checks the code; the table is closed to the
-- public key. New objects only; nothing existing is changed.

create table if not exists public.jeweller_making (
  slug text not null,
  category text not null check (category in ('Ring', 'Earrings', 'Bangle', 'Mangalsutra', 'Chain')),
  pct numeric not null check (pct between 3 and 60),
  updated_at timestamptz not null default now(),
  primary key (slug, category)
);
alter table public.jeweller_making enable row level security;
revoke all on public.jeweller_making from anon, authenticated;

create or replace function public.submit_making_charges(
  code text, ring numeric, earrings numeric, bangle numeric, mangalsutra numeric, chain numeric)
returns text language plpgsql security definer
set search_path = public, extensions as $f$
declare s text;
begin
  select c.slug into s from jeweller_codes c
   where c.code_hash = encode(extensions.digest(coalesce(code, ''), 'sha256'), 'hex');
  if s is null then
    return 'code';
  end if;
  if ring is null and earrings is null and bangle is null and mangalsutra is null and chain is null then
    return 'empty';
  end if;
  -- a making charge on plain gold is a percentage between 3 and 60
  if exists (select 1 from unnest(array[ring, earrings, bangle, mangalsutra, chain]) x
             where x is not null and (x < 3 or x > 60)) then
    return 'range';
  end if;
  insert into jeweller_making(slug, category, pct)
  select s, t.cat, t.pct
    from (values ('Ring', ring), ('Earrings', earrings), ('Bangle', bangle),
                 ('Mangalsutra', mangalsutra), ('Chain', chain)) as t(cat, pct)
   where t.pct is not null
  on conflict (slug, category) do update set pct = excluded.pct, updated_at = now();
  return 'ok';
end $f$;

grant execute on function public.submit_making_charges(text, numeric, numeric, numeric,
  numeric, numeric) to anon, authenticated;

-- A big chain already on the site (e.g. Malabar) that wants to send its
-- making charges needs only a code for its existing brand slug:
--   insert into jeweller_codes (slug, code_hash)
--   values ('<existing slug>', encode(extensions.digest('<code you send them>', 'sha256'), 'hex'));
