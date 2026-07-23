#!/usr/bin/env python3
"""One-off: locate the embedded market-watch data blob in the page source."""
import os
import re
import requests

key = os.environ["ZYTE_API_KEY"].strip()
r = requests.post(
    "https://api.zyte.com/v1/extract", auth=(key, ""),
    json={"url": "https://www.mcxindia.com/market-data/market-watch",
          "browserHtml": True, "geolocation": "IN"},
    headers={"Accept": "application/json"}, timeout=150)
html = r.json().get("browserHtml") or ""
print("html len", len(html))

# JSON-ish occurrences of GOLD with quotes around
for pat in (r'"Symbol"\s*:\s*"GOLD"', r"'Symbol'\s*:\s*'GOLD'",
            r'"GOLD"', r'FUTCOM'):
    ms = list(re.finditer(pat, html))
    print(f"pattern {pat!r}: {len(ms)} hits")
    if ms:
        i = ms[0].start()
        print("  ctx:", re.sub(r"\s+", " ", html[max(0, i-250):i+420])[:640])
        break

# look for var assignments that hold big arrays
for m in re.finditer(r"var\s+(\w+)\s*=\s*(\[|\{)", html):
    name = m.group(1)
    seg = html[m.start():m.start() + 160]
    if re.search(r"Symbol|LTP|Expiry|FUTCOM", html[m.start():m.start() + 3000]):
        print("VAR:", name, "->", re.sub(r"\s+", " ", seg)[:150])
