-- Read-only health check of the database: what exists, no data changed.
-- Run by the db-run workflow; prints names and counts only, never rows.
\pset footer off
select current_database() as db, current_user as connected_as, version();
select routine_name as function from information_schema.routines
 where routine_schema = 'public' order by 1;
select table_name as table from information_schema.tables
 where table_schema = 'public' order by 1;
select (select count(*) from public.unsub_reasons) as unsub_reasons,
       (select count(*) from public.inquiries
         where email is not null and unsub_token is not null) as subscribed_now,
       (select count(*) from public.page_views) as page_views;
select public.analytics_report('wrong-token') as token_check;
