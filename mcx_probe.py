#!/usr/bin/env python3
"""One-off: find the commodity dropdown selector on the market-watch page."""
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
soup = BeautifulSoup(html, "html.parser")

for s in soup.find_all("select"):
    opts = [o.get("value") for o in s.find_all("option")][:6]
    print("SELECT id=%r name=%r class=%r nopts=%d first=%s" %
          (s.get("id"), s.get("name"), " ".join(s.get("class") or []),
           len(s.find_all("option")), opts))

# instrument-type radio/tabs?
for inp in soup.find_all("input"):
    t = inp.get("type")
    if t in ("radio", "button", "submit"):
        print("INPUT type=%s id=%r name=%r value=%r" %
              (t, inp.get("id"), inp.get("name"), inp.get("value")))

# does FUTCOM GOLD already exist anywhere in the DOM text?
txt = soup.get_text(" ")
print("FUTCOM count:", len(re.findall(r"FUTCOM", txt)))
m = re.search(r"FUTCOM\s+GOLD[^A-Z]", txt)
print("FUTCOM GOLD present:", bool(m))
# pagination hints
for a in soup.find_all(["a", "button"]):
    tt = (a.get_text(strip=True) or "")[:20]
    if re.fullmatch(r"\d+|Next|»|>", tt):
        print("PAGER:", a.name, "id=%r" % a.get("id"), "text=%r" % tt)
