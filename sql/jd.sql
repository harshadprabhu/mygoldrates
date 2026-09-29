-- Jewellers Digest (JD) - the B2B subscription product.
-- Run once in Supabase -> SQL Editor. Safe to re-run.
--
-- Everything here is service-role only. RLS is ON with NO anon policy on any
-- table, which means the anon key the public site ships cannot read or write
-- a single row - these hold payment records, entitlements and API key
-- material, and the browser has no business touching them. The JD worker
-- talks to these with the service key from a Cloudflare secret.

-- ------------------------------------------------- rename from b2b_* (JD)
-- This module was originally shipped as "b2b". It is now Jewellers Digest
-- (JD) and every object is named jd_*. If the earlier version of this file
-- was already run, the objects below exist under the old names - rename
-- them in place so the data survives. If it was never run, every branch is
-- a no-op and the create statements further down do the work.
--
-- Renaming is deliberate rather than re-creating: these tables can hold
-- live payment records and issued API keys. Dropping and re-creating would
-- silently revoke every subscriber's key.
do $$
declare
  obj  record;
  cons record;
begin
  -- Every public relation still called b2b_*: tables, their indexes, and the
  -- identity sequences behind their id columns. Swept from the catalog rather
  -- than listed by hand, so nothing is missed because I forgot to add it.
  for obj in
    select c.relname as old_name,
           'jd_' || substring(c.relname from 5) as new_name,
           c.relkind
      from pg_class c
      join pg_namespace ns on ns.oid = c.relnamespace
     where ns.nspname = 'public'
       and c.relname like 'b2b\_%'
       and c.relkind in ('r', 'i', 'S')
       -- Not when the new name is already taken: a half-finished run must be
       -- safe to repeat, and an already-renamed database must not be clobbered
       -- by something stale left lying under the old name.
       and to_regclass('public.jd_' || substring(c.relname from 5)) is null
     order by case c.relkind when 'r' then 1 else 2 end
  loop
    execute format(
      case obj.relkind
        when 'r' then 'alter table public.%I rename to %I'
        when 'i' then 'alter index public.%I rename to %I'
        when 'S' then 'alter sequence public.%I rename to %I'
      end, obj.old_name, obj.new_name);
  end loop;

  -- Constraints (primary keys, foreign keys, uniques) keep their b2b_*
  -- auto-generated names through a table rename. Nothing references them by
  -- name, but leaving them behind means the schema half-says "b2b" forever.
  for cons in
    select t.relname as tbl, c.conname as old_name,
           'jd_' || substring(c.conname from 5) as new_name
      from pg_constraint c
      join pg_class t on t.oid = c.conrelid
      join pg_namespace ns on ns.oid = t.relnamespace
     where ns.nspname = 'public'
       and t.relname like 'jd\_%'
       and c.conname like 'b2b\_%'
  loop
    execute format('alter table public.%I rename constraint %I to %I',
                   cons.tbl, cons.old_name, cons.new_name);
  end loop;

  -- The old triggers survive the table rename and would keep firing
  -- alongside the jd_* ones created below. Same effect, twice; drop them.
  if to_regclass('public.jd_accounts') is not null then
    execute 'drop trigger if exists b2b_accounts_touch on public.jd_accounts';
  end if;
  if to_regclass('public.jd_subscriptions') is not null then
    execute 'drop trigger if exists b2b_subs_touch on public.jd_subscriptions';
  end if;

  if to_regprocedure('public.b2b_touch_updated_at()') is not null
     and to_regprocedure('public.jd_touch_updated_at()') is null then
    execute 'alter function public.b2b_touch_updated_at() '
            'rename to jd_touch_updated_at';
  end if;
end $$;

-- ---------------------------------------------------------------- accounts
create table if not exists public.jd_accounts (
  id            bigint generated always as identity primary key,
  email         text not null,
  business_name text,
  phone         text,
  city          text,
  state         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
-- One account per email, case-insensitively: a jeweller who signs up twice
-- must land on the same account rather than silently paying twice.
create unique index if not exists jd_accounts_email_uidx
  on public.jd_accounts (lower(email));

-- ----------------------------------------------------------- subscriptions
create table if not exists public.jd_subscriptions (
  id                       bigint generated always as identity primary key,
  account_id               bigint not null references public.jd_accounts(id)
                             on delete cascade,
  razorpay_subscription_id text not null,
  razorpay_plan_id         text,
  razorpay_customer_id     text,
  -- Razorpay's own vocabulary, stored verbatim: created, authenticated,
  -- active, pending, halted, cancelled, completed, expired. Not remapped to
  -- our own words - when something goes wrong the value here should match
  -- what the Razorpay dashboard shows, with no translation layer to doubt.
  status                   text not null default 'created',
  current_start            timestamptz,
  current_end              timestamptz,
  charge_count             integer not null default 0,
  last_event_at            timestamptz,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now()
);
create unique index if not exists jd_subs_rzp_uidx
  on public.jd_subscriptions (razorpay_subscription_id);
create index if not exists jd_subs_account_idx
  on public.jd_subscriptions (account_id);

-- --------------------------------------------------------------- payments
create table if not exists public.jd_payments (
  id                  bigint generated always as identity primary key,
  account_id          bigint references public.jd_accounts(id) on delete set null,
  subscription_id     bigint references public.jd_subscriptions(id) on delete set null,
  razorpay_payment_id text not null,
  razorpay_invoice_id text,
  -- Paise, as an integer. Money never goes in a float: 50.00 rupees is 5000
  -- and stays exactly 5000 through every read.
  amount_paise        integer not null,
  currency            text not null default 'INR',
  status              text,
  method              text,
  created_at          timestamptz not null default now()
);
create unique index if not exists jd_payments_rzp_uidx
  on public.jd_payments (razorpay_payment_id);

-- --------------------------------------------------------------- api keys
create table if not exists public.jd_api_keys (
  id           bigint generated always as identity primary key,
  account_id   bigint not null references public.jd_accounts(id) on delete cascade,
  -- Only a SHA-256 hash is stored. The key itself is shown once, at
  -- creation, and is not recoverable afterwards - a leak of this table must
  -- not hand anyone a working key. key_prefix is the first few visible
  -- characters, kept so a jeweller can tell their keys apart in a UI.
  key_prefix   text not null,
  key_hash     text not null,
  active       boolean not null default true,
  created_at   timestamptz not null default now(),
  last_used_at timestamptz
);
create unique index if not exists jd_api_keys_hash_uidx
  on public.jd_api_keys (key_hash);
create index if not exists jd_api_keys_account_idx
  on public.jd_api_keys (account_id);

-- --------------------------------------------------------- webhook events
-- Razorpay retries a webhook until it gets a 2xx, so the same event WILL
-- arrive more than once. The unique index on event_id is what makes
-- processing idempotent: a duplicate insert fails, and the handler treats
-- that failure as "already handled" rather than charging entitlement twice.
create table if not exists public.jd_webhook_events (
  id          bigint generated always as identity primary key,
  event_id    text not null,
  event       text not null,
  payload     jsonb,
  received_at timestamptz not null default now(),
  processed   boolean not null default false,
  error       text
);
create unique index if not exists jd_webhook_events_uidx
  on public.jd_webhook_events (event_id);
create index if not exists jd_webhook_events_recv_idx
  on public.jd_webhook_events (received_at desc);

-- ------------------------------------------------------------------- RLS
-- Enabled with no policies at all. Postgres denies by default, so the anon
-- and authenticated roles get nothing; only the service role (which bypasses
-- RLS) can touch these. This is deliberate: there is no legitimate reason
-- for the public site's key to reach payment or key material.
alter table public.jd_accounts       enable row level security;
alter table public.jd_subscriptions  enable row level security;
alter table public.jd_payments       enable row level security;
alter table public.jd_api_keys       enable row level security;
alter table public.jd_webhook_events enable row level security;

revoke all on public.jd_accounts       from anon, authenticated;
revoke all on public.jd_subscriptions  from anon, authenticated;
revoke all on public.jd_payments       from anon, authenticated;
revoke all on public.jd_api_keys       from anon, authenticated;
revoke all on public.jd_webhook_events from anon, authenticated;

-- ------------------------------------------------------- updated_at touch
create or replace function public.jd_touch_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

drop trigger if exists jd_accounts_touch on public.jd_accounts;
create trigger jd_accounts_touch before update on public.jd_accounts
  for each row execute function public.jd_touch_updated_at();

drop trigger if exists jd_subs_touch on public.jd_subscriptions;
create trigger jd_subs_touch before update on public.jd_subscriptions
  for each row execute function public.jd_touch_updated_at();

-- ----------------------------------------------------------------- notes
-- Storage: create a bucket named `jd-reports` and leave it PRIVATE. The
-- daily workbook is uploaded there by jd_report.py and handed out only as
-- a short-lived signed URL to an account whose subscription is current. A
-- public bucket would make the whole paywall decorative.
--
-- If a bucket named `b2b-reports` was already created under the old module
-- name, rename it in Supabase Storage (or create `jd-reports` and delete the
-- empty one) - Storage buckets are not Postgres objects, so the rename block
-- above cannot reach them.
