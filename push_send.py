#!/usr/bin/env python3
"""Morning gold rate as a phone/browser notification (owner, 9 Nov 2026).

Visitors who tap "Get today's gold rate every morning" on the site (pwa.js)
are subscribed through the browser's standard Web Push: the JD Worker keeps
each subscription as a private file in Supabase Storage
(jd-reports/push/<hash>.json, cf-worker-jd/worker.js). This sends each of
them today's rate, the change since yesterday and the cheapest jeweller
for their city, once a day from the morning run (rates.yml, alerts=true).
Subscriptions the push service says are gone (404/410) are deleted.

The VAPID key pair that signs the notifications is made once and kept in
collector_cache "webpush_vapid" (private; never in git). The site build
reads its public half (vapid_public_key) for pwa.js.

    python push_send.py           # send
    python push_send.py --dry     # print the messages, send nothing
"""
import base64
import json
import os
import sys

KEY = "webpush_vapid"
BUCKET, PREFIX = "jd-reports", "push"
F22 = 22 / 24
SITE = "https://mygoldrates.com"


def _b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def ensure_keys(create=True):
    """(public key as base64url, private key as PEM) or (None, None)."""
    import private_store
    k = private_store.cache_get(KEY) or {}
    if k.get("public") and k.get("private_pem"):
        return k["public"], k["private_pem"]
    if not create or not private_store.client():
        return None, None
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_bytes(serialization.Encoding.X962,
                                         serialization.PublicFormat.UncompressedPoint)
    pem = priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()
    k = {"public": _b64u(pub), "private_pem": pem}
    if not private_store.cache_put(KEY, k):
        return None, None
    print("web push: new signing key made")
    return k["public"], k["private_pem"]


def vapid_public_key():
    """For the site build: the public half, made on first use."""
    try:
        return ensure_keys(create=True)[0] or ""
    except Exception as e:                     # never stops the build
        print(f"web push: no key ({type(e).__name__})")
        return ""


def inr(v):
    s = f"{int(round(v)):d}"
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return "₹" + s


def message(kb, city=""):
    """{title, body, url} for one subscriber, from the Sona data file."""
    r22 = kb["med"]["22K"]
    h = kb.get("hist") or []
    d22 = (h[-1][1] - h[-2][1]) * F22 if len(h) >= 2 else 0
    move = ("unchanged" if abs(d22) < 1 else
            ("▲ " if d22 > 0 else "▼ ") + inr(abs(d22)))
    c = next((x for x in kb.get("cities") or [] if city and x["n"].lower() == city.lower()), None)
    state = c["st"] if c else None
    pool = [b for b in kb["brands"] if b.get("r24") and (b.get("nat") or (state and state in (b.get("st") or [])))]
    pool = pool or [b for b in kb["brands"] if b.get("r24")]
    best = min(pool, key=lambda b: b["r24"])
    where = f" in {c['n']}" if c else ""
    return {"title": f"Gold rate today: 22K {inr(r22)}/g {move}",
            "body": (f"Cheapest{where}: {best['n']} {inr(best['r24'] * F22)}/g for 22K. "
                     f"24K {inr(kb['med']['24K'])}/g. Tap for every jeweller."),
            "url": f"{SITE}{c['u'] if c else '/'}?src=push", "tag": "morning-rate"}


def subscriptions(sb):
    """[(path, subscription dict)] from Storage."""
    out, off = [], 0
    store = sb.storage.from_(BUCKET)
    while True:
        page = store.list(PREFIX, {"limit": 1000, "offset": off}) or []
        for o in page:
            name = o.get("name") or ""
            if not name.endswith(".json"):
                continue
            path = f"{PREFIX}/{name}"
            try:
                out.append((path, json.loads(store.download(path))))
            except Exception:
                pass
        if len(page) < 1000:
            return out
        off += 1000


def main(dry=False):
    import private_store
    sb = private_store.client()
    if not sb:
        print("web push: no Supabase credentials"); return
    pub, pem = ensure_keys(create=False)
    if not pem:
        print("web push: no signing key yet (made by the site build)"); return
    with open("docs/assistant.json", encoding="utf-8") as f:
        kb = json.load(f)
    subs = subscriptions(sb)
    print(f"web push: {len(subs)} subscribers")
    if dry:
        for _, s in subs[:5]:
            print("  ", s.get("city"), json.dumps(message(kb, s.get("city", "")), ensure_ascii=False))
        print("   (no city)", json.dumps(message(kb), ensure_ascii=False))
        return
    from py_vapid import Vapid02
    from pywebpush import WebPushException, webpush
    vapid = Vapid02.from_pem(pem.encode())   # RFC 8292 "vapid t=, k=", which Apple requires
    sent = gone = failed = 0
    for path, s in subs:
        try:
            webpush({"endpoint": s["endpoint"], "keys": s["keys"]},
                    data=json.dumps(message(kb, s.get("city", "")), ensure_ascii=False),
                    vapid_private_key=vapid, vapid_claims={"sub": "mailto:contact@mygoldrates.com"},
                    ttl=6 * 3600, timeout=20)
            sent += 1
        except WebPushException as e:
            code = getattr(e.response, "status_code", None)
            if code in (404, 410):                  # unsubscribed or expired
                try:
                    sb.storage.from_(BUCKET).remove([path])
                except Exception:
                    pass
                gone += 1
            else:
                failed += 1
                print(f"  push failed ({code})")
        except Exception as e:
            failed += 1
            print(f"  push failed ({type(e).__name__})")
    print(f"web push: sent {sent}, removed {gone} expired, {failed} failed")


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
