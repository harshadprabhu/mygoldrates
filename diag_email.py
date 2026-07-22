#!/usr/bin/env python3
"""One-off diagnostic: Brevo account + delivery events + subscriber list.
Emails are masked. Run via the diag-email workflow, then read the log.
"""
import os
import requests
from supabase import create_client


def mask(em):
    if not em or "@" not in em:
        return str(em)
    u, d = em.split("@", 1)
    return (u[:3] + "***") + "@" + d


def main():
    key = os.environ.get("BREVO_API_KEY", "").strip()
    h = {"api-key": key, "accept": "application/json"}

    print("=== BREVO ACCOUNT ===")
    try:
        a = requests.get("https://api.brevo.com/v3/account", headers=h, timeout=30)
        print("http", a.status_code)
        j = a.json()
        print("account email:", j.get("email"))
        print("company:", j.get("companyName"))
        plan = j.get("plan")
        print("plan:", plan)
    except Exception as e:
        print("account error:", repr(e))

    print("\n=== BREVO TRANSACTIONAL EVENTS (last 2 days) ===")
    try:
        e = requests.get(
            "https://api.brevo.com/v3/smtp/statistics/events?days=2&limit=200",
            headers=h, timeout=30)
        print("http", e.status_code)
        evs = e.json().get("events", [])
        if not evs:
            print("(no events returned - nothing sent, or held pre-delivery)")
        for ev in evs:
            print(ev.get("date"), mask(ev.get("email")),
                  "->", ev.get("event"), "|", ev.get("reason", ""))
    except Exception as e:
        print("events error:", repr(e))

    print("\n=== SUBSCRIBERS (inquiries) ===")
    try:
        sb = create_client(os.environ["SUPABASE_URL"],
                           os.environ["SUPABASE_SERVICE_KEY"])
        subs = sb.table("inquiries").select(
            "email,last_emailed,unsub_token,offers_optin").execute().data
        print("count:", len(subs))
        for s in subs:
            print(mask(s.get("email")),
                  "| last_emailed=", s.get("last_emailed"),
                  "| token?", bool(s.get("unsub_token")))
    except Exception as e:
        print("subs error:", repr(e))


if __name__ == "__main__":
    main()
