#!/usr/bin/env python3
"""One-off: inspect the Zyte-rendered MCX market-watch DOM."""
import os
import re
import requests
from bs4 import BeautifulSoup

key = os.environ["ZYTE_API_KEY"].strip()
r = requests.post(
    "https://api.zyte.com/v1/extract", auth=(key, ""),
    json={"url": "https://www.mcxindia.com/market-data/market-watch",
          "browserHtml": True, "geolocation": "IN"},
    headers={"Accept": "application/json"}, timeout=150)
print("zyte status", r.status_code)
html = r.json().get("browserHtml") or ""
print("html len", len(html))
print("title:", re.search(r"<title[^>]*>(.*?)</title>", html, re.S).group(1)[:120]
      if re.search(r"<title[^>]*>(.*?)</title>", html, re.S) else "none")

soup = BeautifulSoup(html, "html.parser")
tables = soup.find_all("table")
print("tables:", len(tables))
for ti, t in enumerate(tables):
    ths = [th.get_text(strip=True) for th in t.find_all("th")]
    trs = t.find_all("tr")
    print(f"table {ti}: rows={len(trs)} ths={ths[:12]}")
    for tr in trs[:3]:
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if cells:
            print("   row:", cells[:10])

n = len(re.findall(r"GOLD", html))
print("literal GOLD occurrences:", n)
for m in list(re.finditer(r"GOLD", html))[:4]:
    i = m.start()
    print("ctx:", re.sub(r"\s+", " ", html[max(0, i - 150):i + 200])[:320])
