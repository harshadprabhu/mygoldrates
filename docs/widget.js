(function(){
var B='https://mygoldrates.com';
function fmt(n){var s=Math.round(n).toString(),o=s.slice(-3),r=s.slice(0,-3);
while(r.length>2){o=r.slice(-2)+','+o;r=r.slice(0,-2);}return '\u20b9'+(r?r+','+o:o);}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function draw(box,d){
  var dark=box.getAttribute('data-theme')==='dark';
  var credit=box.querySelector('a[href^="'+B+'"]');
  var c=d.chg22||0, cs=Math.abs(c)<1?'unchanged':(c>0?'\u25b2 '+fmt(c):'\u25bc '+fmt(-c));
  var cc=Math.abs(c)<1?(dark?'#bbb':'#666'):(c>0?'#1f9d55':'#d64545');
  var fg=dark?'#f3ead2':'#2a2112', bg=dark?'#16130d':'#fffaf0', bd=dark?'#3a3222':'#e8d9b0', mu=dark?'#b9ad8f':'#7a6a48';
  var rows=(d.top||[]).slice(0,box.getAttribute('data-rows')?+box.getAttribute('data-rows'):3).map(function(j){
    var td='padding:3px 0;border:0;background:none;color:'+fg+';font-size:13px';
    return '<tr><td style="'+td+'">'+esc(j.name)+'</td><td style="'+td+';text-align:right">'+fmt(j.r22)+'</td></tr>';}).join('');
  var w=document.createElement('div');
  w.setAttribute('style','font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:'+fg+';background:'+bg+';border:1px solid '+bd+';border-radius:12px;padding:14px 16px;max-width:340px;box-sizing:border-box');
  w.innerHTML='<div style="font-weight:700;font-size:15px;margin-bottom:6px">Gold rate today'+(d.place?' in '+esc(d.place):'')+'</div>'
   +'<div style="display:flex;gap:18px;margin-bottom:4px"><div><div style="font-size:11px;color:'+mu+'">24K / gram</div><div style="font-size:20px;font-weight:700">'+fmt(d.r24)+'</div></div>'
   +'<div><div style="font-size:11px;color:'+mu+'">22K / gram</div><div style="font-size:20px;font-weight:700">'+fmt(d.r22)+'</div></div></div>'
   +'<div style="font-size:12px;color:'+cc+';margin-bottom:8px">22K '+cs+' since yesterday</div>'
   +(rows?'<div style="font-size:11px;color:'+mu+';margin-bottom:2px">Lowest 22K today</div><table style="width:100%;border-collapse:collapse;font-size:13px">'+rows+'</table>':'')
   +'<div style="font-size:11px;color:'+mu+';margin-top:8px">'+esc(d.date)+' \u00b7 before 3% GST and making charges</div>';
  box.innerHTML='';box.appendChild(w);
  if(credit){credit.setAttribute('style','display:inline-block;margin-top:6px;font:12px system-ui,sans-serif;color:'+mu);box.appendChild(credit);}
}
function run(){
  var boxes=document.querySelectorAll('.mygoldrates-widget');
  if(!boxes.length)return;
  boxes.forEach(function(box){
    if(box.getAttribute('data-done'))return;box.setAttribute('data-done','1');
    var city=box.getAttribute('data-city')||'';
    fetch(B+'/widget-data.json',{mode:'cors'}).then(function(r){return r.json();}).then(function(all){
      var d=all.india, p=city&&all.places&&all.places[city];
      if(p){d=JSON.parse(JSON.stringify(d));d.place=p.name;d.top=p.top||d.top;}
      draw(box,d);
    }).catch(function(){});
  });
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else run();
})();
