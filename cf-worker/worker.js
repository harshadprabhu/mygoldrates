/**
 * MyGoldRates scheduler.
 *
 * Cloudflare Cron Triggers fire on time (within seconds), unlike GitHub's
 * scheduled workflows which are delayed 1-2h on private repos. This Worker
 * dispatches the rate collection and the Instagram posts via the GitHub API
 * at the exact IST times (PLAN), and tells the morning run to send the email.
 *
 * Secret required:  GH_PAT  (fine-grained token, repo mygoldrates,
 *                            Actions: Read and write)
 * Crons (UTC) are declared in wrangler.toml.
 */
const OWNER = "harshadprabhu";
// Renamed from "goldrates" - GitHub redirects the old name for now, but
// that's not something to depend on, especially now that this dispatch is
// the SOLE trigger for the daily alert email (see rates.yml).
const REPO = "mygoldrates";
// What runs when (UTC "HH:MM"). GitHub's own schedules run hours late or not
// at all, so everything time-bound is dispatched from here, on time.
// days: 0 = Sunday. The Instagram job posts each kind at most once a day, so a
// late GitHub-scheduled run of the same post does nothing.
const PLAN = {
  "05:30": [{ wf: "rates.yml", inputs: { alerts: "true" } }],    // 11:00 IST, sends the digest
  "03:17": [{ wf: "social.yml", inputs: { post: "news", mode: "post" } }],    // 08:47 IST
  "05:47": [{ wf: "social.yml", inputs: { post: "rates", mode: "post" } }],   // 11:17 IST
  "09:17": [{ wf: "social.yml", inputs: { post: "pulse", mode: "post" } }],   // 14:47 IST
  "11:47": [{ wf: "social.yml", inputs: { post: "deals", mode: "post" } }],   // 17:17 IST
  "13:07": [{ wf: "social.yml", inputs: { post: "reel", mode: "post" } }],    // 18:37 IST
  "13:47": [{ wf: "social.yml", inputs: { post: "awareness", mode: "post" }, days: [2, 4, 6] }], // 19:17 IST
};

// Rates every 30 minutes from 09:00 to 21:00 IST (03:30-15:30 UTC), so the
// board follows the jewellers through the day. 11:00 IST stays the one run
// that sends the alert email.
for (let m = 3 * 60 + 30; m <= 15 * 60 + 30; m += 30) {
  const key = String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
  if (!PLAN[key]) PLAN[key] = [];
  if (!PLAN[key].some((j) => j.wf === "rates.yml")) PLAN[key].push({ wf: "rates.yml", inputs: { alerts: "false" } });
}

async function dispatch(env, wf, inputs) {
  const res = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${wf}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GH_PAT}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "mygoldrates-cron",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main", inputs }),
    }
  );
  // 204 = accepted. Anything else, log for `wrangler tail`.
  if (res.status !== 204) console.log("dispatch failed", wf, res.status, await res.text());
  else console.log("dispatched", wf, JSON.stringify(inputs));
  return res.status;
}

export default {
  async scheduled(event, env, ctx) {
    const t = new Date(event.scheduledTime);
    const key = String(t.getUTCHours()).padStart(2, "0") + ":" + String(t.getUTCMinutes()).padStart(2, "0");
    for (const job of PLAN[key] || []) {
      if (job.days && !job.days.includes(t.getUTCDay())) continue;
      ctx.waitUntil(dispatch(env, job.wf, job.inputs));
    }
  },

  // Optional: hitting the Worker URL in a browser triggers a manual run,
  // handy for testing. Remove if you don't want that.
  async fetch(request, env, ctx) {
    const st = await dispatch(env, "rates.yml", { alerts: "false" });
    return new Response(st === 204 ? "Run dispatched ✅" : `Failed: ${st}`, { status: st === 204 ? 200 : 500 });
  },
};
