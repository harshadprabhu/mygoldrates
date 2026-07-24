# MyGoldRates cron Worker

Fires the `fetch-rates` GitHub workflow **on time** (Cloudflare Cron Triggers
run within seconds), instead of relying on GitHub's delayed scheduler. The
11:00 IST run also sends the daily email digest.

## Setup (dashboard — easiest)

1. **Create a GitHub token** so the Worker can start the job:
   - GitHub → Settings → Developer settings → **Fine-grained tokens** →
     Generate new token.
   - Resource owner: your account. Repository access: **Only select
     repositories → goldrates**.
   - Permissions → Repository → **Actions: Read and write**.
   - Generate and copy it (starts `github_pat_...`).

2. **Create the Worker:**
   - Cloudflare dashboard → **Workers & Pages** → **Create** → **Create
     Worker** → name it `mygoldrates-cron` → Deploy.
   - **Edit code** → paste the contents of `worker.js` → **Deploy**.

3. **Add the token as a secret:**
   - Worker → **Settings** → **Variables and Secrets** → **Add** →
     type **Secret**, name **`GH_PAT`**, value = the token → Save.

4. **Add the cron triggers:**
   - Worker → **Settings** → **Triggers** → **Cron Triggers** → add three:
     `30 5 * * *`, `30 8 * * *`, `30 11 * * *`  (UTC = 11:00 / 14:00 /
     17:00 IST).

5. **Test now:** open the Worker's `*.workers.dev` URL in a browser — it
   should say “Run dispatched ✅”, and a run appears under the repo's
   **Actions** tab within seconds.

## Setup (CLI alternative)

```bash
cd cf-worker
npx wrangler deploy
npx wrangler secret put GH_PAT     # paste the token when prompted
```
Cron triggers come from `wrangler.toml` automatically.

## Notes

- The GitHub-native schedule in `.github/workflows/rates.yml` stays as a
  backup; if the Worker ever fails, GitHub still runs (just later).
- The daily email is guarded to send **once per day** regardless of how many
  runs fire, so the backup can't cause duplicate emails.
