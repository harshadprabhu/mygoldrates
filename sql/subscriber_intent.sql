-- What a subscriber is buying for, and when (2026-11-01, approved by the owner).
--
-- Sona offers a price-drop alert after answering about prices or deals; the
-- signup popup asks two optional questions after subscribing. Both write
-- here, to the subscriber's own row, only through save_intent() below. New
-- columns only; nothing existing changes. The consent line the visitor agreed
-- to is stored with the time, as India's DPDP Act expects.

alter table public.inquiries add column if not exists buy_for      text;        -- wedding | festival | investment | gift | self
alter table public.inquiries add column if not exists buy_when     text;        -- this_month | 3_months | tracking
alter table public.inquiries add column if not exists interest     jsonb;       -- {"brand","cat","city","karat"} from what they asked Sona
alter table public.inquiries add column if not exists intent_at    timestamptz;
alter table public.inquiries add column if not exists consent_at   timestamptz;
alter table public.inquiries add column if not exists consent_text text;

create or replace function public.save_intent(
  p_email text, p_buy_for text default null, p_buy_when text default null,
  p_interest jsonb default null, p_consent text default null)
returns text language plpgsql security definer
set search_path = public as $f$
declare em text := lower(nullif(trim(p_email), ''));
begin
  if em is null or em !~ '^[^\s@]+@[^\s@]+\.[^\s@]+$' then
    return 'email';
  end if;
  if p_buy_for is not null and p_buy_for not in ('wedding', 'festival', 'investment', 'gift', 'self') then
    return 'buy_for';
  end if;
  if p_buy_when is not null and p_buy_when not in ('this_month', '3_months', 'tracking') then
    return 'buy_when';
  end if;
  if p_interest is not null and (jsonb_typeof(p_interest) <> 'object' or length(p_interest::text) > 400) then
    return 'interest';
  end if;
  update inquiries i set
    buy_for      = coalesce(p_buy_for, i.buy_for),
    buy_when     = coalesce(p_buy_when, i.buy_when),
    interest     = case when p_interest is null then i.interest
                        else coalesce(i.interest, '{}'::jsonb) || p_interest end,
    intent_at    = now(),
    consent_at   = case when p_consent is not null then now() else i.consent_at end,
    consent_text = coalesce(left(p_consent, 300), i.consent_text),
    updated_at   = now()
  where lower(i.email) = em;
  if not found then
    return 'subscribe';
  end if;
  return 'ok';
end $f$;

revoke all on function public.save_intent(text, text, text, jsonb, text) from public;
grant execute on function public.save_intent(text, text, text, jsonb, text) to anon, authenticated;
