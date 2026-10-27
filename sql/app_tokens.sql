-- Private store for app tokens that renew themselves (the Instagram token,
-- refreshed by social_post.py every run). Only the service key can read or
-- write it; nothing existing is changed.
create table if not exists public.app_tokens (
  name text primary key,
  value text not null,
  updated_at timestamptz not null default now()
);
alter table public.app_tokens enable row level security;
revoke all on public.app_tokens from anon, authenticated;
notify pgrst, 'reload schema';
