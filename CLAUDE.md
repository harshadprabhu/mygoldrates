# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A fully automated gold-rate comparison platform for India. Three Python scripts run on GitHub Actions, write to Supabase, and publish a static site to `docs/` (served via Cloudflare Pages at mygoldrates.com).

## Running scripts locally

All scripts need env vars from the GitHub repo secrets. Minimum set:
```bash
export SUPABASE_URL=...
export SUPABASE_SERVICE_KEY=...
```

```bash
pip install -r requirements.txt
playwright install --with-deps chromium   # only needed for scrape.py

python scrape.py           # fetch today's rates for all active brands
python generate_site.py    # rebuild all HTML in docs/
python send_alerts.py      # send daily digest (needs BREVO_API_KEY + ALERTS_FROM)
python scrape_charges.py   # refresh making-charges.json (needs ZYTE_API_KEY)
python list_brands.py      # print brands table (read-only, good sanity check)
```

To send a test email without touching the subscriber list:
```bash
export TEST_EMAIL=you@example.com
export BREVO_API_KEY=...
python test_send.py
```

To seed regional brands into the DB (edit `REGIONAL_BRANDS` in `seed_brands.py` first):
```bash
python seed_brands.py
```

Syntax-check `generate_site.py` before pushing (it's a large f-string-heavy file where bare `{`/`}` in JS cause cryptic SyntaxErrors):
```bash
python -c "import ast; ast.parse(open('generate_site.py',encoding='utf-8').read()); print('OK')"
```

## Architecture

### Data flow
```
scrape.py  →  Supabase (rates table)
                  ↓
generate_site.py  →  docs/*.html  →  git commit → Cloudflare Pages
                  ↓
send_alerts.py  →  Brevo API  →  subscriber emails
```

### scrape.py
- Reads active brands from the `brands` table (name, slug, domain, rate_url, active, includes_gst).
- For each brand: fetches its rate page, extracts gold prices by purity using structural HTML parsing (`<tr>` rows first, character-window proximity as fallback).
- Two-layer sanity check: purity-ordering invariant (24K > 22K > 18K) + outlier detection against the day's median.
- Brands in `NEEDS_PROXY` (tanishq, malabar, caratlane, whp, joyalukkas) are fetched via Zyte API.
- Any brand still without a live rate at the end gets a `status: "estimated"` row with the day's median as a placeholder, re-tried each run.
- Upserts into `rates` table keyed on `(brand_id, rate_date)`.

### generate_site.py
- Reads `rates` (joined with `brands`) + fetches live AKGSMA/IBJA/MCX data + news.
- Generates the full site: `index.html`, 100+ city/state pages, calculators, about/contact/inquiry/unsubscribe pages, news pages, sitemaps.
- **Critical:** the file is one large Python module. HTML templates are stored as module-level constants (`TEMPLATE`, `NAV`, `BASE_CSS`, `UNSUB_TEMPLATE`, etc.) using f-strings and `string.Template`. All JavaScript `{` / `}` inside f-strings must be doubled (`{{` / `}}`); inside `Template` strings they must not be. Mixing these up causes silent misrenderings or `SyntaxError` at runtime.
- `REGION_MAP` (dict of slug → list of state names) marks regional jewellers. `send_alerts.py` uses it to exclude regional brands from the national median.
- `LOCATIONS` drives the city/state page generation — add entries here to add new city pages.

### send_alerts.py
- `latest_published_rates(sb)` fetches the most recently published day within the last 10 days — carries forward Friday's rates over weekends and holidays rather than skipping.
- Filters to national brands only (excludes slugs in `REGION_MAP`) for the email median/lowest.
- Per-subscriber `last_emailed` guard (set only on successful send) prevents duplicate emails when multiple morning runs fire.
- Missing `BREVO_API_KEY` → `sys.exit(1)` (intentionally loud). Whole-batch failure → `sys.exit(1)`.

### Cloudflare Worker (`cf-worker/`)
- A Cloudflare Cron Trigger fires at 11:00/14:00/17:00 IST (UTC 05:30/08:30/11:30) and dispatches the `fetch-rates` GitHub Actions workflow via the GitHub API.
- The morning run (11:00 IST) passes `alerts=true` so `send_alerts.py` runs; afternoon runs pass `alerts=false`.
- This bypasses GitHub's scheduled-workflow delays (often 30–120 min on private repos).
- Needs a Cloudflare secret `GH_PAT` (fine-grained PAT with Actions read/write on this repo).
- Deploy: Actions → `deploy-worker` workflow.

## Supabase schema (key tables)

**`brands`** — jeweller catalogue. `slug` is the stable identifier used in `NEEDS_PROXY`, `REGION_MAP`, and URL paths. `active=false` brands are skipped by the scraper.

**`rates`** — one row per `(brand_id, rate_date)`. `status` is `published` (real scraped rate), `estimated` (market-median placeholder), or `quarantined` (outlier). The email and site only use `published` rows.

**`inquiries`** — subscribers. Key columns: `email` (unique case-insensitive index), `unsub_token` (UUID, required for the email unsubscribe link), `last_emailed` (date, cleared to `null` to re-include someone in the next send).

**`unsub_reasons`** — unsubscribe feedback (reason text only, no PII). Populated by the `save_unsub_reason(t, reason)` RPC called from the unsubscribe page before the actual `unsubscribe(t)` RPC.

## GitHub Actions workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `rates.yml` | CF Worker cron (via `workflow_dispatch`) + 4 morning GitHub crons | scrape → build site → publish → email |
| `charges.yml` | 1st & 16th of month | scrape making charges → update `docs/making-charges.json` |
| `deploy.yml` | manual | push `docs/` to Cloudflare Pages without scraping |
| `deploy-worker.yml` | manual | deploy `cf-worker/` to Cloudflare Workers |
| `cf-domain.yml` | manual (inspect/switch mode) | manage Cloudflare DNS for mygoldrates.com |
| `seed-brands.yml` | manual | run `seed_brands.py` |
| `list-brands.yml` | manual | run `list_brands.py` |
| `test-send.yml` | manual (needs `email` input) | send a test digest to one address |

## Required GitHub secrets

`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `BREVO_API_KEY`, `ALERTS_FROM`, `ZYTE_API_KEY`, `GOOGLE_CLIENT_ID`, `ADSENSE_CLIENT`, `ADSENSE_SLOT`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `CF_WORKERS_TOKEN` (for Worker deploy), `GH_PAT` (set in Cloudflare Worker secrets, not GitHub).

## SQL migrations

`sql/` holds one-off SQL files intended to be pasted into the Supabase SQL Editor:
- `upsert_subscriber.sql` — schema + `upsert_subscriber` RPC (run once on setup).
- `unsub_reason.sql` — `unsub_reasons` table + `save_unsub_reason` RPC.
- `resubscribe_all.sql` — clears `last_emailed` for all subscribers (re-sends to everyone on next run).

## Adding a new brand

1. Add a row to `REGIONAL_BRANDS` in `seed_brands.py` (or insert directly into `brands` table).
2. If it's regional, add its slug to `REGION_MAP` in `generate_site.py`.
3. If it's behind an anti-bot wall, add its slug to `NEEDS_PROXY` in `scrape.py` (requires `ZYTE_API_KEY`).
4. Run `seed-brands` workflow (or `python seed_brands.py` locally with env vars set).

## Known pitfalls

- **f-string brace escaping**: `generate_site.py` has JS inside Python f-strings. Every literal `{` or `}` in JS must be `{{` / `}}`. This has caused production build failures — always syntax-check before pushing.
- **Cloudflare deploy step in `rates.yml`**: the `if: ${{ env.CF_TOKEN != '' }}` guard evaluates before step-level env is applied, so `CF_TOKEN` is always empty there — the step never runs from `rates.yml`. Use the dedicated `deploy.yml` workflow to redeploy the site to Cloudflare Pages.
- **GitHub scheduled workflow delays**: GitHub delays scheduled runs 30–120 min on private repos. The Cloudflare Worker is the reliable trigger; the GitHub crons in `rates.yml` are a fallback.
