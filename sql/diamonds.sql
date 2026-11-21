-- Diamond jewellery products (owner, 21 Nov 2026). The raw, like-for-like
-- data behind the diamond comparison: each product's 4Cs, natural vs
-- lab-grown, certifier, and the diamond / metal / making price split.
-- diamonds.py collect refreshes today's rows each run. Private (business
-- data), so it lives in Supabase, never git. Run once in the SQL Editor.
create table if not exists public.diamonds (
  id            bigint generated always as identity primary key,
  captured_on   date not null default (now() at time zone 'Asia/Kolkata')::date,
  brand         text not null,
  url           text not null,
  carat         numeric,
  band          text,
  clarity       text,
  color         text,
  type          text,            -- 'natural' | 'lab-grown'
  cert          text,            -- IGI | GIA | SGL | BIS
  diamond_price numeric,
  metal_value   numeric,
  making        numeric,
  total         numeric,
  per_carat     numeric,         -- diamond_price / carat
  created_at    timestamptz not null default now()
);
create index if not exists diamonds_day   on public.diamonds (captured_on);
create index if not exists diamonds_brand on public.diamonds (brand, type, band);
revoke all on public.diamonds from anon, authenticated;
