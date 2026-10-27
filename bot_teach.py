#!/usr/bin/env python3
"""Sona learns from what she could not answer.

Every morning, before bot_learn.py exports the approved answers, this job
reads the recent questions Sona could not answer or that got a thumbs-down
(bot_questions, private), asks Gemini's free text model to write a short
answer for each one using only the site's own knowledge file, and saves the
ones that pass the checks below as approved answers (bot_answers). The owner
can remove any of them on the analytics page.

Checks, because a wrong answer is worse than none:
  - no figures: rates and charges change every day, so a learned answer may
    not quote one; it points to the page with today's figure instead (karat
    and purity marks such as 22K or 916 are allowed);
  - a link must be a real page of the site;
  - nothing Gemini is unsure of: it skips anything off-topic, personal or
    not covered by the site's facts;
  - the stored question is a general rewording, never the visitor's words,
    because the approved answers are exported to the public repo.

Only counts are printed - the repo and its run logs are public.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

KB = "docs/assistant.json"
SITE = "docs"
MAX_NEW = 15
IST = timezone(timedelta(hours=5, minutes=30))
MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]

ALLOWED_FIGURES = re.compile(r"\b(?:24|22|18|14)\s?(?:k|kt|karat|carat)\b|\b(?:999|916|750|585)\b|\b6-digit\b|\b3\s?%",
                             re.I)
BANNED = ("scrap", "guarantee")

PROMPT = """You help Sona, the free assistant on mygoldrates.com, an Indian site that \
compares the gold rates, making charges and offers that jewellers publish. Below are \
visitor questions Sona could not answer, or answered badly. For each one, write the \
answer Sona should give in future.

Rules:
- Use ONLY the facts in SITE FACTS. If they do not cover the question, or it is \
off-topic, personal, abusive or about a specific order, skip it.
- Never write any number, price, rate, percentage or date (gold rates change every \
day). Instead point to the page that shows today's figure. Karat and purity marks \
(22K, 24K, 916) are fine.
- 1 to 3 short, friendly sentences in plain English, at most 350 characters.
- "u": one link from SITE PAGES that helps most, or "".
- "q": a short, general English question that this answer is for, in your own words \
(never copy the visitor's wording, names or details).
- Skip anything ALREADY ANSWERED covers.

Reply with JSON only: a list of {"i": <question number>, "q": "...", "a": "...", "u": "..."} \
for the questions you answer; leave out the ones you skip.

SITE FACTS
%s

SITE PAGES
%s

ALREADY ANSWERED
%s

VISITOR QUESTIONS
%s
"""


def say(msg):
    """A notice in the run's summary on GitHub (counts only), plain print elsewhere."""
    print(("::notice title=bot_teach::" if os.environ.get("GITHUB_ACTIONS") else "") + msg)


def norm(t):
    return re.sub(r"[^a-z0-9 ]+", "", (t or "").lower()).strip()


def site_pages():
    """'/learn/gold-hallmarking' style paths of every page in docs/."""
    out = ["/"]
    for root, _, files in os.walk(SITE):
        for f in files:
            if f.endswith(".html") and f not in ("404.html", "analytics.html"):
                p = os.path.relpath(os.path.join(root, f), SITE)[:-5]
                p = p[:-len("index")].rstrip("/") if p.endswith("index") else p
                out.append("/" + p if p else "/")
    return sorted(set(out))


def facts(kb):
    """The parts of Sona's knowledge file that do not change daily."""
    lines = [f"- The site compares {len(kb['brands'])} jewellers' published rates across "
             f"{len(kb['cities'])} cities, updated every morning, free, no sign-up."]
    lines += [f"- Q: {f['q']} A: {f['a']}" + (f" (page {f['u']})" if f.get("u") else "") for f in kb.get("faq", [])]
    lines += [f"- Guide {g['u']}: {g['t']} - {g['d']}" for g in kb.get("guides", [])]
    lines.append("- Jewellers: " + ", ".join(sorted({b.get("n", "") for b in kb["brands"] if b.get("n")})))
    lines.append("- Cities: " + ", ".join(sorted({c.get("n", "") for c in kb["cities"] if c.get("n")})))
    return "\n".join(lines)


def check(item, pages, n_questions):
    """The cleaned answer, or None if it fails a check."""
    try:
        i, q, a, u = int(item["i"]), item["q"].strip(), item["a"].strip(), (item.get("u") or "").strip()
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    if not (0 <= i < n_questions) or not (8 <= len(q) <= 200) or not (20 <= len(a) <= 400):
        return None
    if re.search(r"\d", ALLOWED_FIGURES.sub("", a + " " + q)):
        return None                                   # a figure that would go stale
    if any(w in (a + q).lower() for w in BANNED):
        return None
    if u and u.split("#")[0].split("?")[0] not in pages:
        u = ""
    return {"q": q, "a": a, "u": u}


def ask_gemini(prompt, key):
    import requests
    for m in MODELS:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                              headers={"x-goog-api-key": key},
                              json={"contents": [{"parts": [{"text": prompt}]}],
                                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}},
                              timeout=120)
        except requests.RequestException as e:
            say(f"{m} no answer ({type(e).__name__})"); continue
        if not r.ok:
            msg = r.json().get("error", {}).get("message", "") if "json" in r.headers.get("content-type", "") else ""
            say(f"{m} HTTP {r.status_code} {msg[:160]}"); continue
        try:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            out = json.loads(text)
            return out if isinstance(out, list) else []
        except (KeyError, IndexError, ValueError):
            say(f"{m} gave no usable JSON")
    return None


def pending(rows):
    """Latest row per question; keep it only if Sona still failed it."""
    latest = {}
    for r in sorted(rows, key=lambda r: r["created_at"]):
        if (r.get("page") or "").startswith("/__"):
            continue                                  # the owner's own tests
        latest[r["q_norm"]] = r
    return [r["q"] for r in latest.values() if not r["answered"] or r.get("helpful") is False]


def main():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        say("no GEMINI_API_KEY - skipped"); return
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    days = int(os.environ.get("TEACH_DAYS") or 2)
    since = (datetime.now(IST) - timedelta(days=days)).date().isoformat()
    rows = sb.table("bot_questions").select("q, q_norm, answered, helpful, page, created_at") \
             .gte("day", since).limit(5000).execute().data
    qs = pending(rows)[:60]
    say(f"{len(qs)} questions to look at from the last {days} days")
    if not qs:
        return
    known = sb.table("bot_answers").select("q, a").eq("active", True).execute().data
    kb = json.load(open(KB, encoding="utf-8"))
    pages = site_pages()
    prompt = PROMPT % (facts(kb), "\n".join(pages),
                       "\n".join(f"- {k['q']}" for k in known) or "(none)",
                       "\n".join(f"{i}. {q}" for i, q in enumerate(qs)))
    out = ask_gemini(prompt, key)
    if out is None:
        say("Gemini unavailable - nothing learned today"); return
    seen = {norm(k["q"]) for k in known}
    new, rejected = [], 0
    for item in out:
        c = check(item, pages, len(qs))
        if not c or norm(c["q"]) in seen:
            rejected += 1; continue
        seen.add(norm(c["q"])); new.append(c)
    new = new[:MAX_NEW]
    for c in new:
        sb.table("bot_answers").insert({"q": c["q"], "a": c["a"], "u": c["u"] or None}).execute()
    say(f"{len(new)} new answers saved, {rejected} drafts failed the checks, "
          f"{len(qs) - len(out)} skipped by Gemini")


if __name__ == "__main__":
    main()
