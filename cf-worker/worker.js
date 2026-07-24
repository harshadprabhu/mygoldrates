/**
 * MyGoldRates scheduler.
 *
 * Cloudflare Cron Triggers fire on time (within seconds), unlike GitHub's
 * scheduled workflows which are delayed 1-2h on private repos. This Worker
 * dispatches the `fetch-rates` workflow via the GitHub API at the exact IST
 * times, and tells the morning run to send the daily email.
 *
 * Secret required:  GH_PAT  (fine-grained token, repo goldrates,
 *                            Actions: Read and write)
 * Crons (UTC) are declared in wrangler.toml.
 */
const OWNER = "harshadprabhu";
const REPO = "goldrates";
const WORKFLOW = "rates.yml"; // the workflow FILE name (not its display name)
const MORNING_CRON = "30 5 * * *"; // 11:00 IST -> this run emails the digest

export default {
  async scheduled(event, env, ctx) {
    const alerts = event.cron === MORNING_CRON ? "true" : "false";
    const res = await fetch(
      `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/` +
        `${WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GH_PAT}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "mygoldrates-cron",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: "main", inputs: { alerts } }),
      }
    );
    // 204 = accepted. Anything else, log for `wrangler tail`.
    if (res.status !== 204) {
      console.log("dispatch failed", res.status, await res.text());
    } else {
      console.log(`dispatched (${event.cron}, alerts=${alerts})`);
    }
  },

  // Optional: hitting the Worker URL in a browser triggers a manual run,
  // handy for testing. Remove if you don't want that.
  async fetch(request, env, ctx) {
    const res = await fetch(
      `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/` +
        `${WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GH_PAT}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "mygoldrates-cron",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: "main", inputs: { alerts: "false" } }),
      }
    );
    return new Response(
      res.status === 204 ? "Run dispatched ✅" : `Failed: ${res.status}`,
      { status: res.status === 204 ? 200 : 500 }
    );
  },
};
