-- One-off: make everyone in `inquiries` eligible for the next alert run again,
-- then re-send by triggering the fetch-rates workflow (Actions -> fetch-rates
-- -> Run workflow) or running send_alerts.py.
--
-- send_alerts.py emails a subscriber when they have an email + unsub_token and
-- last_emailed is null or older than today. Clearing last_emailed re-includes
-- everyone still on the list for the next run.
--
-- NOTE: this cannot bring back people whose unsubscribe removed their row or
-- cleared their unsub_token - that data is gone. It only re-alerts current rows.

-- If unsubscribe clears unsub_token (rather than deleting the row), regenerate
-- tokens for any row missing one so they become eligible again. Safe no-op if
-- all rows already have a token. Requires pgcrypto's gen_random_uuid (default
-- on Supabase).
update public.inquiries
   set unsub_token = gen_random_uuid()::text
 where unsub_token is null and email is not null;

-- Re-include everyone for the next send.
update public.inquiries
   set last_emailed = null;
