(function(){
  var SKIP=/^\/(inquiry|unsubscribe|list-your-jewellery|jd-today|jewellers-digest|analytics|404)(\.html)?\/?$/;
  if(SKIP.test(location.pathname))return;
  function g(k){try{return localStorage.getItem(k)}catch(_){return null}}
  function s(k,v){try{localStorage.setItem(k,v)}catch(_){}}
  function sg(k){try{return sessionStorage.getItem(k)}catch(_){return null}}
  function ss(k,v){try{sessionStorage.setItem(k,v)}catch(_){}}
  function eligible(){
    if(g('gr_sub')==='1'||sg('gr_dismissed'))return false;
    var n=parseInt(g('gr_pop_n')||'0',10)||0,last=parseInt(g('gr_pop_last')||'0',10)||0;
    return n<3&&!(last&&Date.now()-last<7*864e5);
  }
  if(!eligible())return;
  var css='#grPop{position:fixed;inset:0;z-index:9000;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(0,0,0,.55)}'+
    '#grPop .b{position:relative;width:100%;max-width:400px;max-height:calc(100vh - 32px);overflow:auto;background:#1b1712;color:#f3eadb;border:1px solid rgba(212,166,60,.35);border-radius:18px;padding:22px 20px 16px;font:14px/1.5 "DM Sans",system-ui,sans-serif;box-shadow:0 24px 64px rgba(0,0,0,.5)}'+
    '#grPop .t{font:700 18px/1.3 "Playfair Display",Georgia,serif;margin:4px 30px 6px 0}'+
    '#grPop .d{font-size:13px;opacity:.75;margin-bottom:12px}'+
    '#grPop input{display:block;width:100%;box-sizing:border-box;margin:0 0 8px;padding:11px 12px;border-radius:10px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.05);color:inherit;font-size:15px}'+
    '#grPop .go{width:100%;padding:12px;border:0;border-radius:10px;background:#d4a63c;color:#1a1405;font-weight:700;font-size:15px;cursor:pointer}'+
    '#grPop .go[disabled]{opacity:.6}'+
    '#grPop .x{position:absolute;top:10px;right:10px;width:32px;height:32px;border:0;border-radius:8px;background:rgba(255,255,255,.08);color:inherit;font-size:20px;cursor:pointer}'+
    '#grPop .l{display:block;width:100%;margin-top:6px;background:none;border:0;color:inherit;opacity:.6;font-size:12px;cursor:pointer;padding:6px}'+
    '#grPop .st{min-height:16px;font-size:12px;margin-top:6px}'+
    '#grPop .n{font-size:11px;opacity:.55;text-align:center;margin-top:6px}'+
    '@media(max-width:760px){#grPop{align-items:flex-end;padding:0;background:rgba(0,0,0,.35)}'+
    '#grPop .b{max-width:none;max-height:72vh;border-radius:18px 18px 0 0;border-bottom:0;animation:grUp .3s ease}}'+
    '@keyframes grUp{from{transform:translateY(100%)}to{transform:none}}';
  var el,armed=true,timer;
  function build(){
    var st=document.createElement('style');st.textContent=css;document.head.appendChild(st);
    el=document.createElement('div');el.id='grPop';el.setAttribute('role','dialog');
    el.setAttribute('aria-modal','true');el.setAttribute('aria-labelledby','grPopT');
    el.innerHTML='<div class="b"><button class="x" type="button" aria-label="Close">&times;</button>'+
      '<div class="t" id="grPopT">Get today’s gold rate every morning</div>'+
      '<div class="d">One free email: the cheapest jeweller near you, the market rate and what moved gold. Unsubscribe anytime.</div>'+
      '<input id="grPopN" type="text" placeholder="Your name" autocomplete="name">'+
      '<input id="grPopE" type="email" placeholder="Your email *" inputmode="email" autocomplete="email">'+
      '<input id="grPopP" type="tel" placeholder="Mobile number *" inputmode="tel" autocomplete="tel" maxlength="18" value="+91 ">'+
      '<button class="go" type="button">Subscribe free</button>'+
      '<div class="st" aria-live="polite"></div>'+
      '<div class="n">Free. No spam. One-click unsubscribe.</div>'+
      '<button class="l" type="button">Maybe later</button></div>';
    document.body.appendChild(el);
    el.querySelector('.x').onclick=close;el.querySelector('.l').onclick=close;
    el.addEventListener('click',function(e){if(e.target===el)close()});
    document.addEventListener('keydown',function(e){if(e.key==='Escape'&&el.parentNode)close()});
    el.querySelector('.go').onclick=submit;
  }
  function open(){
    if(!armed)return;armed=false;
    clearTimeout(timer);window.removeEventListener('scroll',onScroll);
    if(!eligible())return;
    if(document.querySelector('#credential_picker_container,iframe[src*="accounts.google.com/gsi"]'))return;
    build();
    s('gr_pop_last',String(Date.now()));
    s('gr_pop_n',String((parseInt(g('gr_pop_n')||'0',10)||0)+1));
    setTimeout(function(){try{document.getElementById('grPopE').focus({preventScroll:true})}catch(_){}},150);
  }
  function close(){if(el&&el.parentNode)el.parentNode.removeChild(el);ss('gr_dismissed','1');}
  function msg(t,ok){var m=el.querySelector('.st');m.style.color=ok?'#7fd1a3':'#f0909e';m.textContent=t;}
  function save(p){
    if(window.GR_SAVE)return window.GR_SAVE(p);
    var SB=(window.GR_SB_URL||'').replace(/\/$/,''),K=window.GR_SB_KEY||'';
    return fetch(SB+'/rest/v1/rpc/upsert_subscriber',{method:'POST',
      headers:{'Content-Type':'application/json',apikey:K,Authorization:'Bearer '+K},
      body:JSON.stringify({payload:p})}).then(function(r){if(!r.ok)throw new Error('save');return true});
  }
  function submit(){
    var b=this,e=document.getElementById('grPopE').value.trim();
    var d=document.getElementById('grPopP').value.replace(/\D/g,'');
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e))return msg('Enter a valid email');
    if(d==='91'||d==='0'||d==='091')d='';
    else{if(d.length>10&&d.slice(0,2)==='91')d=d.slice(2);if(d.length===11&&d.charAt(0)==='0')d=d.slice(1);}
    if(!d)return msg('Mobile number is required');
    if(!/^[6-9]\d{9}$/.test(d))return msg('Enter a valid 10-digit mobile number');
    b.disabled=true;b.textContent='Subscribing…';
    save({email:e,phone:'+91'+d,name:document.getElementById('grPopN').value.trim(),
          country:'India',signup_method:'popup'}).then(function(){
      s('gr_sub','1');b.textContent='Subscribed ✓';
      msg('✓ Subscribed — your first email arrives tomorrow morning.',true);
      setTimeout(function(){if(el&&el.parentNode)el.parentNode.removeChild(el)},2200);
    }).catch(function(){b.disabled=false;b.textContent='Subscribe free';
      msg('Couldn’t save that — please try again in a moment.')});
  }
  function onScroll(){
    var h=document.documentElement.scrollHeight-innerHeight;
    if(h>0&&(scrollY||0)/h>0.12)open();
  }
  timer=setTimeout(open,5000);
  window.addEventListener('scroll',onScroll,{passive:true});
})();
