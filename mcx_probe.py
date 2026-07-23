#!/usr/bin/env python3
"""One-off: scan page JS globals / DataTables for the market-watch dataset."""
import os
import re
import requests

JS = """
var el=document.createElement('pre');el.id='grx-mcx';var out=[];
try{
 for(var k in window){
  try{var v=window[k];
   if(v&&typeof v==='object'&&typeof v.length==='number'&&v.length>5&&v[0]&&
      typeof v[0]==='object'&&v[0].Symbol!==undefined){
     out.push('GLOBAL '+k+' len='+v.length+' keys='+Object.keys(v[0]).join(','));
     var g=[].filter.call(v,function(x){return String(x.Symbol).toUpperCase().indexOf('GOLD')===0;});
     if(g.length)out.push('GOLDDATA '+k+' '+JSON.stringify(g.slice(0,6)));
   }}catch(e){}}
 if(window.jQuery&&jQuery.fn&&jQuery.fn.DataTable){
   jQuery('table').each(function(i){
     try{var dt=jQuery(this).DataTable();var data=dt.rows().data().toArray();
       out.push('DT '+i+' rows='+data.length);
       var g=data.filter(function(x){var s=JSON.stringify(x);return s.indexOf('GOLD')>=0;});
       if(g.length)out.push('DTGOLD '+i+' '+JSON.stringify(g.slice(0,4)));
     }catch(e){}});
 }
}catch(e){out.push('ERR '+e);}
el.textContent=out.join('\\n---\\n').slice(0,250000);
document.body.appendChild(el);
"""

key = os.environ["ZYTE_API_KEY"].strip()
r = requests.post(
    "https://api.zyte.com/v1/extract", auth=(key, ""),
    json={"url": "https://www.mcxindia.com/market-data/market-watch",
          "browserHtml": True, "geolocation": "IN",
          "actions": [
              {"action": "waitForTimeout", "timeout": 6},
              {"action": "evaluate", "source": JS},
              {"action": "waitForTimeout", "timeout": 2}]},
    headers={"Accept": "application/json"}, timeout=170)
print("zyte status", r.status_code)
html = r.json().get("browserHtml") or ""
m = re.search(r'<pre id="grx-mcx">(.*?)</pre>', html, re.S)
if not m:
    print("no pre; html len", len(html))
    raise SystemExit()
raw = m.group(1).replace("&amp;", "&").replace("&lt;", "<") \
       .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
for chunk in raw.split("\n---\n"):
    print(chunk[:800])
    print("=====")
