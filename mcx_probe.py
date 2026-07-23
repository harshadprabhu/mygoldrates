#!/usr/bin/env python3
"""One-off: apply GOLD filter via Zyte actions, check the rendered table."""
import os
import re
import requests
from bs4 import BeautifulSoup

JS = """
function pick(id, vals){var s=document.querySelector(id);if(!s)return 'no '+id;
 var opts=[].map.call(s.options,function(o){return o.value});
 var v=null;for(var i=0;i<vals.length;i++){if(opts.indexOf(vals[i])>=0){v=vals[i];break;}}
 if(!v)return 'noopt '+id+' '+opts.slice(0,8).join(',');
 if(window.jQuery){jQuery(id).val(v).trigger('change');}
 else{s.value=v;s.dispatchEvent(new Event('change',{bubbles:true}));}
 return 'set '+id+'='+v;}
pick('#ddlInstrumentName',['FUTCOM']);
pick('#ddlSymbol',['gold','GOLD','Gold']);
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
j = r.json()
for a in j.get("actions", []):
    print("action:", a.get("action"), "->", a.get("status", ""),
          str(a.get("error", ""))[:120])
html = j.get("browserHtml") or ""
print("html len", len(html))
soup = BeautifulSoup(html, "html.parser")
for ti, t in enumerate(soup.find_all("table")):
    ths = [th.get_text(strip=True) for th in t.find_all("th")]
    trs = t.find_all("tr")
    print(f"table {ti}: rows={len(trs)} ths={ths[:12]}")
    for tr in trs[1:6]:
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if cells:
            print("   row:", cells[:12])
