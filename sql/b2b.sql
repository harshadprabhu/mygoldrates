-- B2B subscription product. Run once in Supabase -> SQL Editor.
--
-- Everything here is service-role only. RLS is ON with NO anon policy on any
-- table, which means the anon key the public site ships cannot read or write
-- a single row - these hold payment records, entitlements and API key
-- material, and the browser has no business touching them. The B2B worker
-- talks to these with the service key from a Cloudflare secret.

-- ---------------------------------------------------------------- accounts
create table if not exists public.b2b_accounts (
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
create unique index if not exists b2b_accounts_email_uidx
  on public.b2b_accounts (lower(email));

-- ----------------------------------------------------------- subscriptions
create table if not exists public.b2b_subscriptions (
  id                       bigint generated always as identity primary key,
  account_id               bigint not null references public.b2b_accounts(id)
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
create unique index if not exists b2b_subs_rzp_uidx
  on public.b2b_subscriptions (razorpay_subscription_id);
create index if not exists b2b_subs_account_idx
  on public.b2b_subscriptions (account_id);

-- --------------------------------------------------------------- payments
create table if not exists public.b2b_payments (
  id                  bigint generated always as identity primary key,
  account_id          bigint references public.b2b_accounts(id) on delete set null,
  subscription_id     bigint references public.b2b_subscriptions(id) on delete set null,
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
create unique index if not exists b2b_payments_rzp_uidx
  on public.b2b_payments (razorpay_payment_id);

-- --------------------------------------------------------------- api keys
create table if not exists public.b2b_api_keys (
  id           bigint generated always as identity primary key,
  account_id   bigint not null references public.b2b_accounts(id) on delete cascade,
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
create unique index if not exists b2b_api_keys_hash_uidx
  on public.b2b_api_keys (key_hash);
create index if not exists b2b_api_keys_account_idx
  on public.b2b_api_keys (account_id);

-- --------------------------------------------------------- webhook events
-- Razorpay retries a webhook until it gets a 2xx, so the same event WILL
-- arrive more than once. The unique index on event_id is what makes
-- processing idempotent: a duplicate insert fails, and the handler treats
-- that failure as "already handled" rather than charging entitlement twice.
create table if not exists public.b2b_webhook_events (
  id          bigint generated always as identity primary key,
  event_id    text not null,
  event       text not null,
  payload     jsonb,
  received_at timestamptz not null default now(),
  processed   boolean not null default false,
  error       text
);
create unique index if not exists b2b_webhook_events_uidx
  on public.b2b_webhook_events (event_id);
create index if not exists b2b_webhook_events_recv_idx
  on public.b2b_webhook_events (received_at desc);

-- ------------------------------------------------------------------- RLS
-- Enabled with no policies at all. Postgres denies by default, so the anon
-- and authenticated roles get nothing; only the service role (which bypasses
-- RLS) can touch these. This is deliberate: there is no legitimate reason
-- for the public site's key to reach payment or key material.
alter table public.b2b_accounts       enable row level security;
alter table public.b2b_subscriptions  enable row level security;
alter table public.b2b_payments       enable row level security;
alter table public.b2b_api_keys       enable row level security;
alter table public.b2b_webhook_events enable row level security;

revoke all on public.b2b_accounts       from anon, authenticated;
revoke all on public.b2b_subscriptions  from anon, authenticated;
revoke all on public.b2b_payments       from anon, authenticated;
revoke all on public.b2b_api_keys       from anon, authenticated;
revoke all on public.b2b_webhook_events from anon, authenticated;

-- ------------------------------------------------------- updated_at touch
create or replace function public.b2b_touch_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

drop trigger if exists b2b_accounts_touch on public.b2b_accounts;
create trigger b2b_accounts_touch before update on public.b2b_accounts
  for each row execute function public.b2b_touch_updated_at();

drop trigger if exists b2b_subs_touch on public.b2b_subscriptions;
create trigger b2b_subs_touch before update on public.b2b_subscriptions
  for each row execute function public.b2b_touch_updated_at();

-- ----------------------------------------------------------------- notes
-- Storage: create a bucket named `b2b-reports` and leave it PRIVATE. The
-- daily workbook is uploaded there by b2b_report.py and handed out only as
-- a short-lived signed URL to an account whose subscription is current. A
-- public bucket would make the whole paywall decorative.
