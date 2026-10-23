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
  // Links in the daily email carry ?from=alert: whoever arrives through one
  // is a subscriber, so never show them the popup (on this device, ever).
  try{var q=new URLSearchParams(location.search);
    if(q.get('from')==='alert'){s('gr_sub','1');q.delete('from');
      history.replaceState(null,'',location.pathname+(q.toString()?'?'+q:'')+location.hash);}}catch(_){}
  if(!eligible())return;
  // Same design as the homepage popup: gold header with a preview of the
  // morning email, three benefits, one strong button. Closes only from the
  // small x in the corner (or Escape) - no tap-outside, no "Maybe later".
  // The x stays visible; on phones it is a bottom sheet that leaves the
  // top of the page on screen.
  var css='#grPop{position:fixed;inset:0;z-index:9000;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(6,4,2,.66);backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px)}'+
    '#grPop .b{position:relative;width:100%;max-width:400px;max-height:calc(100vh - 32px);overflow:auto;background:#17130d;color:#f3eadb;border:1px solid rgba(240,208,128,.28);border-radius:20px;font:14px/1.5 "DM Sans",system-ui,sans-serif;box-shadow:0 28px 70px rgba(0,0,0,.6);animation:grIn .3s ease}'+
    '#grPop .x{position:absolute;top:6px;right:6px;z-index:2;width:28px;height:28px;border:0;background:none;color:rgba(26,20,5,.55);font-size:16px;line-height:1;cursor:pointer;padding:0}'+
    '#grPop .x:hover{color:#1a1405}'+
    '#grPop .h{position:relative;padding:20px 20px 16px;background:radial-gradient(120% 140% at 0% 0%,#ffe9a8 0%,#e7bf5a 38%,#b98a24 100%);color:#1a1405;overflow:hidden;border-radius:20px 20px 0 0}'+
    '#grPop .pl{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.12em;background:rgba(26,20,5,.88);color:#f0d080;border-radius:999px;padding:4px 10px}'+
    '#grPop .t{font:800 21px/1.22 "Playfair Display",Georgia,serif;margin:10px 0 0;max-width:300px}'+
    '#grPop .m{margin-top:14px;background:#fffaf0;border-radius:12px;padding:10px 12px;box-shadow:0 8px 22px rgba(80,55,0,.28);transform:rotate(-1.2deg);font-size:11.5px;color:#4b4030}'+
    '#grPop .m .mh{font-size:10.5px;color:#7a6a48;font-weight:600}#grPop .m .mh i{display:inline-block;width:8px;height:8px;border-radius:50%;background:#2fa36b;margin-right:6px}'+
    '#grPop .m .ms{font-size:13px;font-weight:800;color:#1a1405;margin-top:3px}'+
    '#grPop .m .mr{display:flex;justify-content:space-between;margin-top:6px}#grPop .m .tg{font-size:9.5px;font-weight:800;color:#1f7a4d;background:#dff3e8;border-radius:5px;padding:2px 6px}'+
    '#grPop .bd{padding:16px 20px}'+
    '#grPop ul{list-style:none;margin:0 0 12px;padding:0}#grPop li{position:relative;padding:3px 0 3px 26px;font-size:13px;line-height:1.4}'+
    '#grPop li:before{content:"✓";position:absolute;left:0;top:3px;width:18px;height:18px;border-radius:50%;background:rgba(212,166,60,.18);color:#f0d080;font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center}'+
    '#grPop .d{font-size:12px;opacity:.7;margin-bottom:10px}'+
    '#grPop input{display:block;width:100%;box-sizing:border-box;margin:0 0 8px;padding:11px 12px;border-radius:10px;border:1px solid rgba(240,208,128,.22);background:rgba(255,255,255,.06);color:inherit;font-size:15px}'+
    '#grPop input:focus{outline:none;border-color:#e7bf5a}'+
    '#grPop .go{width:100%;padding:13px;border:0;border-radius:12px;background:linear-gradient(135deg,#f6d77d,#d4a63c 55%,#b98a24);color:#1a1405;font-weight:800;font-size:15px;cursor:pointer;box-shadow:0 8px 22px rgba(212,166,60,.35)}'+
    '#grPop .go[disabled]{opacity:.6}'+
    '#grPop .st{min-height:16px;font-size:12px;margin-top:6px;text-align:center}'+
    '#grPop .n{font-size:10.5px;opacity:.55;text-align:center;margin-top:6px}'+
    '#grPop .l{display:block;margin:4px auto 0;background:none;border:0;color:inherit;opacity:.45;font-size:10.5px;cursor:pointer;padding:4px 6px;text-decoration:underline;text-underline-offset:2px}'+
    '@media(max-width:760px){#grPop{align-items:flex-end;padding:0;background:rgba(0,0,0,.4);backdrop-filter:none;-webkit-backdrop-filter:none}'+
    '#grPop .b{max-width:none;max-height:78vh;border-radius:20px 20px 0 0;border-bottom:0;animation:grUp .32s ease}}'+
    '@keyframes grUp{from{transform:translateY(100%)}to{transform:none}}@keyframes grIn{from{transform:translateY(16px);opacity:0}to{transform:none;opacity:1}}';
  var el,armed=true,timer;
  function build(){
    var st=document.createElement('style');st.textContent=css;document.head.appendChild(st);
    el=document.createElement('div');el.id='grPop';el.setAttribute('role','dialog');
    el.setAttribute('aria-modal','true');el.setAttribute('aria-labelledby','grPopT');
    el.innerHTML='<div class="b"><button class="x" type="button" aria-label="Close">&times;</button>'+
      '<div class="h"><span class="pl">FREE DAILY GOLD ALERT</span>'+
      '<div class="t" id="grPopT">Know the cheapest gold rate before you buy</div>'+
      '<div class="m" aria-hidden="true"><div class="mh"><i></i>MyGoldRates &middot; every morning</div>'+
      '<div class="ms">Today’s cheapest 22K near you</div>'+
      '<div class="mr"><span>Lowest jeweller rate in your city</span><span class="tg">CHEAPEST</span></div>'+
      '<div class="mr"><span>Market rate &amp; what moved gold</span></div></div></div>'+
      '<div class="bd"><ul><li>The cheapest jeweller in your city, before you leave home</li>'+
      '<li>Today’s market rate and what moved gold overnight</li>'+
      '<li>A heads-up when gold moves sharply</li></ul>'+
      '<div class="d">One short email a day. Takes 10 seconds to join.</div>'+
      '<input id="grPopN" type="text" placeholder="Your name" autocomplete="name">'+
      '<input id="grPopE" type="email" placeholder="Your email *" inputmode="email" autocomplete="email">'+
      '<input id="grPopP" type="tel" placeholder="Mobile number *" inputmode="tel" autocomplete="tel" maxlength="18" value="+91 ">'+
      '<button class="go" type="button">Send me tomorrow’s rates — free</button>'+
      '<div class="st" aria-live="polite"></div>'+
      '<div class="n">&#128274; Free &middot; No spam &middot; One-click unsubscribe in every email</div>'+
      '<button class="l" type="button">Already subscribed?</button></div></div>';
    document.body.appendChild(el);
    el.querySelector('.x').onclick=close;
    // Subscribed on another phone or browser: remember it on this one.
    el.querySelector('.l').onclick=function(){s('gr_sub','1');close();};
    document.addEventListener('keydown',function(e){if(e.key==='Escape'&&el.parentNode)close()});
    el.querySelector('.go').onclick=submit;
    // Signed up with Google but no mobile yet: they are subscribed, so ask
    // only for the number.
    var u=null;try{u=JSON.parse(g('gr_user')||'null')}catch(_){}
    if(g('gr_sub_nophone')==='1'&&u&&u.email){
      el.querySelector('.t').textContent='One last thing: your mobile number';
      el.querySelector('.d').textContent='We have '+u.email+'. Add your mobile so we can reach you if a rate moves sharply.';
      document.getElementById('grPopE').value=u.email;
      if(u.name)document.getElementById('grPopN').value=u.name;
    }
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
    }).catch(function(){b.disabled=false;b.textContent='Send me tomorrow’s rates — free';
      msg('Couldn’t save that — please try again in a moment.')});
  }
  function onScroll(){
    var h=document.documentElement.scrollHeight-innerHeight;
    if(h>0&&(scrollY||0)/h>0.12)open();
  }
  timer=setTimeout(open,5000);
  window.addEventListener('scroll',onScroll,{passive:true});
})();
