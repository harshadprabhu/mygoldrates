#!/usr/bin/env python3
"""One-off: call GetMarketWatch from inside the page session, read from DOM."""
import json
import os
import re
import requests

JS = """
fetch('https://www.mcxindia.com/backpage.aspx/GetMarketWatch',{method:'POST',
 credentials:'include',
 headers:{'Content-Type':'application/json; charset=UTF-8',
  'Accept':'application/json, text/javascript, */*; q=0.01',
  'X-Requested-With':'XMLHttpRequest'},body:'{}'})
 .then(function(r){return r.text();})
 .then(function(t){var el=document.createElement('pre');el.id='grx-mcx';
   el.textContent=t.slice(0,300000);document.body.appendChild(el);})
 .catch(function(e){var el=document.createElement('pre');el.id='grx-mcx';
   el.textContent='ERR '+e;document.body.appendChild(el);});
"""

key = os.environ["ZYTE_API_KEY"].strip()
r = requests.post(
    "https://api.zyte.com/v1/extract", auth=(key, ""),
    json={"url": "https://www.mcxindia.com/market-data/market-watch",
          "browserHtml": True, "geolocation": "IN",
          "actions": [
              {"action": "waitForTimeout", "timeout": 4},
              {"action": "evaluate", "source": JS},
              {"action": "waitForTimeout", "timeout": 8}]},
    headers={"Accept": "application/json"}, timeout=170)
print("zyte status", r.status_code)
html = r.json().get("browserHtml") or ""
m = re.search(r'<pre id="grx-mcx">(.*?)</pre>', html, re.S)
if not m:
    print("no grx-mcx pre found; html len", len(html))
    raise SystemExit()
raw = m.group(1)
# unescape basic entities bs-free
raw = raw.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">") \
         .replace("&quot;", '"').replace("&#39;", "'")
print("payload head:", raw[:220])
try:
    d = json.loads(raw).get("d")
    if isinstance(d, str):
        d = json.loads(d)
    if isinstance(d, dict):
        print("d keys:", list(d.keys())[:12])
        d = d.get("Data") or d.get("data") or []
    print("items:", len(d))
    if d:
        print("first keys:", list(d[0].keys()))
    for x in d:
        if str(x.get("Symbol", "")).upper() in ("GOLD", "GOLDM") \
           and str(x.get("InstrumentName", "")).upper() in ("FUTCOM", ""):
            print("GOLDROW:", json.dumps(
                {k: x.get(k) for k in ("Symbol", "InstrumentName",
                                       "ExpiryDate", "LTP", "AbsoluteChange",
                                       "PercentChange", "Unit")}))
except Exception as e:
    print("parse error:", type(e).__name__, str(e)[:200])
