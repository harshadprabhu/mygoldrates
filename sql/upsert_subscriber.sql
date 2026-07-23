-- Run once in Supabase → SQL Editor.
-- Lets a Google sign-in (or the alert form) create/merge a subscriber by
-- email so the same person is one row that keeps gaining data, never a
-- duplicate. Runs as SECURITY DEFINER so the anon key can call it without
-- broad UPDATE rights on the table.

-- 1) columns used by the merge (safe to re-run)
alter table inquiries add column if not exists area text;
alter table inquiries add column if not exists signup_method text default 'manual';
alter table inquiries add column if not exists google_id text;
alter table inquiries add column if not exists google_email_verified boolean;
alter table inquiries add column if not exists picture_url text;
alter table inquiries add column if not exists locale text;
alter table inquiries add column if not exists gender text;
alter table inquiries add column if not exists birthday text;
alter table inquiries add column if not exists updated_at timestamptz default now();
alter table inquiries add column if not exists last_emailed date;
alter table inquiries add column if not exists unsub_token uuid default gen_random_uuid();
update inquiries set unsub_token = gen_random_uuid() where unsub_token is null;

-- 2) de-duplicate any existing rows that share an email (keep newest), then
--    enforce one row per email (case-insensitive)
with ranked as (
  select id, lower(email) le,
         row_number() over (partition by lower(email)
                            order by coalesce(updated_at, now()) desc, id desc) rn
  from inquiries where email is not null and email <> ''
)
delete from inquiries where id in (select id from ranked where rn > 1);

create unique index if not exists inquiries_email_uidx
  on inquiries (lower(email));

-- 3) the upsert-by-email function the site calls (rpc/upsert_subscriber)
create or replace function upsert_subscriber(payload jsonb)
returns void language plpgsql security definer set search_path = public as $$
declare em text := lower(nullif(trim(payload->>'email'), ''));
begin
  if em is null then
    raise exception 'email required';
  end if;
  insert into inquiries as i (
    name, email, phone, country, state, city, zip, area, offers_optin,
    signup_method, google_id, google_email_verified, picture_url, locale,
    gender, birthday, updated_at)
  values (
    nullif(trim(payload->>'name'), ''), payload->>'email',
    nullif(trim(payload->>'phone'), ''), nullif(trim(payload->>'country'), ''),
    nullif(trim(payload->>'state'), ''), nullif(trim(payload->>'city'), ''),
    nullif(trim(payload->>'zip'), ''), nullif(trim(payload->>'area'), ''),
    coalesce((payload->>'offers_optin')::boolean, true),
    coalesce(nullif(trim(payload->>'signup_method'), ''), 'manual'),
    nullif(trim(payload->>'google_id'), ''),
    (payload->>'google_email_verified')::boolean,
    nullif(trim(payload->>'picture_url'), ''),
    nullif(trim(payload->>'locale'), ''),
    nullif(trim(payload->>'gender'), ''),
    nullif(trim(payload->>'birthday'), ''),
    now())
  on conflict (lower(email)) do update set
    -- only overwrite when the incoming value is present; keep existing otherwise
    name                  = coalesce(excluded.name, i.name),
    phone                 = coalesce(excluded.phone, i.phone),
    country               = coalesce(excluded.country, i.country),
    state                 = coalesce(excluded.state, i.state),
    city                  = coalesce(excluded.city, i.city),
    zip                   = coalesce(excluded.zip, i.zip),
    area                  = coalesce(excluded.area, i.area),
    offers_optin          = excluded.offers_optin,
    signup_method         = case when excluded.signup_method = 'google'
                                 then 'google' else i.signup_method end,
    google_id             = coalesce(excluded.google_id, i.google_id),
    google_email_verified = coalesce(excluded.google_email_verified,
                                     i.google_email_verified),
    picture_url           = coalesce(excluded.picture_url, i.picture_url),
    locale                = coalesce(excluded.locale, i.locale),
    gender                = coalesce(excluded.gender, i.gender),
    birthday              = coalesce(excluded.birthday, i.birthday),
    updated_at            = now();
end$$;

grant execute on function upsert_subscriber(jsonb) to anon;
