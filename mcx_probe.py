#!/usr/bin/env python3
"""One-off: POST GetMarketWatch through Zyte's IN proxy, inspect the JSON."""
import base64
import json
import os
import re
import requests

key = os.environ["ZYTE_API_KEY"].strip()
r = requests.post(
    "https://api.zyte.com/v1/extract", auth=(key, ""),
    json={"url": "https://www.mcxindia.com/backpage.aspx/GetMarketWatch",
          "httpResponseBody": True,
          "httpRequestMethod": "POST",
          "httpRequestText": "{}",
          "customHttpRequestHeaders": [
              {"name": "Content-Type",
               "value": "application/json; charset=UTF-8"},
              {"name": "Accept",
               "value": "application/json, text/javascript, */*; q=0.01"},
              {"name": "Referer",
               "value": "https://www.mcxindia.com/market-data/market-watch"},
              {"name": "Origin", "value": "https://www.mcxindia.com"},
              {"name": "X-Requested-With", "value": "XMLHttpRequest"}],
          "geolocation": "IN"},
    headers={"Accept": "application/json"}, timeout=150)
print("zyte status", r.status_code)
if r.status_code != 200:
    print("zyte err:", r.text[:300])
    raise SystemExit()
body = base64.b64decode(r.json()["httpResponseBody"]).decode("utf-8", "replace")
print("body len", len(body))
print("body head:", body[:300])
try:
    d = json.loads(body).get("d")
    if isinstance(d, str):
        d = json.loads(d)
    if isinstance(d, dict):
        print("d keys:", list(d.keys())[:10])
        d = d.get("Data") or d.get("data") or []
    print("items:", len(d))
    if d:
        print("first item keys:", list(d[0].keys()))
    for x in d:
        if str(x.get("Symbol", "")).upper() in ("GOLD", "GOLDM"):
            print("GOLD row:", {k: x.get(k) for k in
                                ("Symbol", "ExpiryDate", "LTP",
                                 "AbsoluteChange", "PercentChange")})
except Exception as e:
    print("parse error:", type(e).__name__, str(e)[:200])
    m = re.search(r"GOLD", body)
    if m:
        print("ctx:", body[max(0, m.start() - 200):m.start() + 300])
