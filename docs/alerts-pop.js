(function(){
  var SKIP=/^\/(inquiry|unsubscribe|list-your-jewellery|jd-today|jewellers-digest|analytics|404)(\.html)?\/?$/;
  if(SKIP.test(location.pathname))return;
  // The homepage and city pages carry their own popup; never show two.
  if(document.getElementById('subPop'))return;
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
  // Filled in by the build: today's 22K gap between the cheapest and the
  // dearest jeweller, today's lowest 22K, and the Google client id.
  var GAP=Number('290')||0,LOW=Number('12958')||0,GCID='459957139537-m6fl4clp90lua3ad2baupf20utkof6fl.apps.googleusercontent.com';
  if(GCID.indexOf('__')===0)GCID='';
  function inr(n){return '₹'+Math.round(n).toLocaleString('en-IN');}
  // Sign-up funnel events for the private analytics dashboard.
  function ev(t){try{if(window.GR_TRACK)window.GR_TRACK('click_events',
    {page:location.pathname,target:'funnel:'+t,session_id:window.GR_SID||''});}catch(_){}}
  // Same design as the homepage popup. One step: Continue with Google, or an
  // email, with an optional price-drop alert; the mobile is asked for after,
  // optionally. Closes only from the small x in the top-left corner (or
  // Escape), and the first press shows what they would miss.
  var css='#grPop{position:fixed;inset:0;z-index:9000;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(6,4,2,.66);backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px)}'+
    '#grPop .b{position:relative;width:100%;max-width:400px;max-height:calc(100vh - 32px);overflow:auto;background:#17130d;color:#f3eadb;border:1px solid rgba(240,208,128,.28);border-radius:20px;font:14px/1.5 "DM Sans",system-ui,sans-serif;box-shadow:0 28px 70px rgba(0,0,0,.6);animation:grIn .3s ease}'+
    '#grPop [hidden]{display:none!important}'+
    // Host pages style short class names of their own (.dn is a price-down
    // marker in pink); keep their colours off the popup's text.
    '#grPop :where(div,p,span,li,label,b){color:inherit}'+
    '#grPop .x{position:absolute;top:6px;left:6px;z-index:2;width:28px;height:28px;border:0;background:none;color:rgba(26,20,5,.55);font-size:16px;line-height:1;cursor:pointer;padding:0}'+
    '#grPop .x:hover{color:#1a1405}'+
    '#grPop .h{position:relative;padding:30px 20px 16px;background:radial-gradient(120% 140% at 0% 0%,#ffe9a8 0%,#e7bf5a 38%,#b98a24 100%);color:#1a1405;overflow:hidden;border-radius:20px 20px 0 0}'+
    '#grPop .pl{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.12em;background:rgba(26,20,5,.88);color:#f0d080;border-radius:999px;padding:4px 10px}'+
    '#grPop .t{font:800 21px/1.22 "Playfair Display",Georgia,serif;margin:10px 0 0;max-width:300px}'+
    '#grPop .m{margin-top:14px;background:#fffaf0;border-radius:12px;padding:10px 12px;box-shadow:0 8px 22px rgba(80,55,0,.28);transform:rotate(-1.2deg);font-size:11.5px;color:#4b4030}'+
    '#grPop .m .mh{font-size:10.5px;color:#7a6a48;font-weight:600}#grPop .m .mh i{display:inline-block;width:8px;height:8px;border-radius:50%;background:#2fa36b;margin-right:6px}'+
    '#grPop .m .ms{font-size:13px;font-weight:800;color:#1a1405;margin-top:3px}'+
    '#grPop .m .mr{display:flex;justify-content:space-between;margin-top:6px}#grPop .m .tg{font-size:9.5px;font-weight:800;color:#1f7a4d;background:#dff3e8;border-radius:5px;padding:2px 6px}'+
    '#grPop .bd{padding:16px 20px}'+
    '#grPop ul{list-style:none;margin:0 0 12px;padding:0}#grPop li{position:relative;padding:3px 0 3px 26px;font-size:13px;line-height:1.4}'+
    '#grPop li:before{content:"✓";position:absolute;left:0;top:3px;width:18px;height:18px;border-radius:50%;background:rgba(212,166,60,.18);color:#f0d080;font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center}'+
    '#grPop .gg{display:flex;justify-content:center;min-height:44px;margin:4px 0 2px}'+
    '#grPop .or{display:flex;align-items:center;gap:10px;font-size:11px;opacity:.6;margin:10px 0 8px}#grPop .or:before,#grPop .or:after{content:"";flex:1;height:1px;background:rgba(240,208,128,.25)}'+
    '#grPop input[type=email],#grPop input[type=tel]{display:block;width:100%;box-sizing:border-box;margin:0 0 8px;padding:11px 12px;border-radius:10px;border:1px solid rgba(240,208,128,.22);background:rgba(255,255,255,.06);color:inherit;font-size:15px}'+
    '#grPop input:focus{outline:none;border-color:#e7bf5a}'+
    '#grPop .pr{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;font-size:12.5px;cursor:pointer;line-height:1.3;margin:2px 0 4px}'+
    '#grPop .pr input[type=checkbox]{width:16px;height:16px;accent-color:#d4a63c;margin:0}'+
    '#grPop .pr .pv{display:inline-flex;align-items:center;gap:3px;color:#f0d080;font-weight:700}'+
    '#grPop .pr .pv input{width:82px;background:rgba(255,255,255,.06);border:1px solid rgba(240,208,128,.3);border-radius:7px;color:inherit;font:inherit;font-weight:700;padding:4px 6px}'+
    '#grPop .ph{font-size:10.5px;opacity:.55;margin:0 0 8px 24px}'+
    '#grPop .go{width:100%;padding:13px;border:0;border-radius:12px;background:linear-gradient(135deg,#f6d77d,#d4a63c 55%,#b98a24);color:#1a1405;font-weight:800;font-size:15px;cursor:pointer;box-shadow:0 8px 22px rgba(212,166,60,.35)}'+
    '#grPop .go[disabled]{opacity:.6}'+
    '#grPop .st{min-height:16px;font-size:12px;margin-top:6px;text-align:center}'+
    '#grPop .n{font-size:10.5px;opacity:.55;text-align:center;margin-top:6px}'+
    '#grPop .l{display:block;margin:4px auto 0;background:none;border:0;color:inherit;opacity:.45;font-size:10.5px;cursor:pointer;padding:4px 6px;text-decoration:underline;text-underline-offset:2px}'+
    '#grPop .sr,#grPop .gpd{padding:30px 20px 18px;text-align:center}'+
    '#grPop .k{font-size:11px;font-weight:800;letter-spacing:.12em;color:#f0d080}'+
    '#grPop .bg{font:800 22px/1.25 "Playfair Display",Georgia,serif;margin:8px 0 6px}#grPop .bg b{color:#f0d080}'+
    '#grPop .sb{font-size:13px;opacity:.8;margin:0 0 14px}'+
    '#grPop .mz{list-style:none;margin:0 0 16px;padding:12px 14px;text-align:left;background:rgba(224,110,110,.07);border:1px solid rgba(224,110,110,.22);border-radius:12px}'+
    '#grPop .mz li:before{content:"✕";background:none;color:#e88b8b;width:auto;height:auto;left:2px;font-size:12px}'+
    '#grPop .no{display:block;margin:10px auto 0;background:none;border:0;color:inherit;opacity:.6;font-size:12px;cursor:pointer;padding:6px 8px}'+
    '#grPop .tk{width:48px;height:48px;margin:0 auto 6px;border-radius:50%;background:linear-gradient(135deg,#f6d77d,#b98a24);color:#1a1405;font-size:26px;font-weight:900;display:flex;align-items:center;justify-content:center}'+
    '#grPop .op{text-align:left;background:rgba(255,255,255,.04);border:1px solid rgba(240,208,128,.18);border-radius:12px;padding:12px}'+
    '#grPop .op .ot{font-size:13px;font-weight:700}#grPop .op .ot span{font-weight:400;opacity:.6}#grPop .op .od{font-size:11.5px;opacity:.6;margin:2px 0 8px}'+
    '@media(max-width:760px){#grPop{align-items:flex-end;padding:0;background:rgba(0,0,0,.4);backdrop-filter:none;-webkit-backdrop-filter:none}'+
    '#grPop .b{max-width:none;max-height:78vh;border-radius:20px 20px 0 0;border-bottom:0;animation:grUp .32s ease}}'+
    '@keyframes grUp{from{transform:translateY(100%)}to{transform:none}}@keyframes grIn{from{transform:translateY(16px);opacity:0}to{transform:none;opacity:1}}';
  var el,armed=true,timer,waits=0,step='main',sureShown=false,doneEmail='';
  function $q(c){return el.querySelector(c);}
  function show(name){step=name;$q('.mn').hidden=name!=='main';$q('.sr').hidden=name!=='sure';
    $q('.gpd').hidden=name!=='done';$q('.b').scrollTop=0;}
  // First press of x (or Escape) shows what they would miss; the second,
  // or "No thanks", closes. After signing up, x just closes.
  function tryClose(){
    if(step==='done'){remove();return;}
    if(sureShown){close();return;}
    sureShown=true;ev('sure_shown');show('sure');
  }
  function build(){
    var st=document.createElement('style');st.textContent=css;document.head.appendChild(st);
    el=document.createElement('div');el.id='grPop';el.setAttribute('role','dialog');
    el.setAttribute('aria-modal','true');el.setAttribute('aria-labelledby','grPopT');
    var target=LOW?Math.floor(LOW*0.98/50)*50:0;
    el.innerHTML='<div class="b"><button class="x" id="spClose" type="button" aria-label="Close">&times;</button>'+
      '<div class="mn"><div class="h"><span class="pl">FREE DAILY GOLD ALERT</span>'+
      '<div class="t" id="grPopT">Know the cheapest gold rate before you buy</div>'+
      '<div class="m" aria-hidden="true"><div class="mh"><i></i>MyGoldRates &middot; every morning</div>'+
      '<div class="ms">Today’s cheapest 22K near you</div>'+
      '<div class="mr"><span>Lowest jeweller rate in your city</span><span class="tg">CHEAPEST</span></div>'+
      '<div class="mr"><span>Market rate &amp; what moved gold</span></div></div></div>'+
      '<div class="bd"><ul><li>The cheapest jeweller in your city, before you leave home</li>'+
      '<li>An email the day gold drops to your price</li></ul>'+
      '<div class="gg" id="grPopG"></div><div class="or"><span>or use your email</span></div>'+
      '<input id="grPopE" type="email" placeholder="Your email" inputmode="email" autocomplete="email">'+
      (target?'<label class="pr"><input type="checkbox" id="grPopPrOn" checked><span>Also email me when 22K drops below</span>'+
        '<span class="pv">&#8377;<input id="grPopPr" type="number" inputmode="numeric" min="3000" max="30000" step="50" value="'+target+'" aria-label="Target 22K rate per gram">/g</span></label>'+
        '<div class="ph">Today’s lowest 22K: '+inr(LOW)+'/g (before GST)</div>':'')+
      '<button class="go" id="alBtnP" type="button">Send me tomorrow’s rates — free</button>'+
      '<div class="st" aria-live="polite"></div>'+
      '<div class="n">&#128274; Free &middot; No spam &middot; One-click unsubscribe in every email</div>'+
      '<button class="l" id="spHave" type="button">Already subscribed?</button></div></div>'+
      '<div class="sr" hidden><div class="k">BEFORE YOU GO</div>'+
      '<div class="bg">'+(GAP>=50?'Today, 22K gold cost up to <b>'+inr(GAP)+'/g</b> more at some jewellers':'Jewellers don’t all charge the same for gold')+'</div>'+
      '<p class="sb">'+(GAP>=50?'On a 10 g chain that’s <b>'+inr(GAP*10)+'</b>, before making charges and GST. The alert tells you who is cheapest every morning.':'The gap between the cheapest and the dearest jeweller changes every day. The alert tells you who is cheapest each morning.')+'</p>'+
      '<ul class="mz"><li>Which jeweller is cheapest in your city each morning</li><li>An email the day gold drops to your price</li><li>Today’s market rate, without searching for it</li></ul>'+
      '<button class="go" id="spSureYes" type="button">Okay, send me the free alerts</button>'+
      '<button class="no" id="spSureNo" type="button">No thanks, close</button></div>'+
      '<div class="gpd" hidden><div class="tk">&#10003;</div><div class="bg">You’re in!</div>'+
      '<p class="sb" id="grPopDone">Your first email arrives tomorrow morning.</p>'+
      '<div class="op"><div class="ot">Add your mobile number <span>(optional)</span></div>'+
      '<div class="od">For rate alerts by SMS or WhatsApp when we launch them. We never call or share it.</div>'+
      '<input id="spPhone" type="tel" placeholder="+91 mobile number" inputmode="tel" autocomplete="tel" maxlength="18">'+
      '<button class="go" id="spPhoneSave" type="button">Save my number</button>'+
      '<div class="st" id="grPopPhSt"></div></div>'+
      '<button class="no" id="spDoneClose" type="button">Done</button></div></div>';
    document.body.appendChild(el);
    $q('.x').onclick=tryClose;
    // Subscribed on another phone or browser: remember it on this one.
    $q('#spHave').onclick=function(){s('gr_sub','1');close();};
    $q('#spSureYes').onclick=function(){show('main');try{document.getElementById('grPopE').focus()}catch(_){}};
    $q('#spSureNo').onclick=close;
    $q('#spDoneClose').onclick=remove;
    $q('#spPhoneSave').onclick=savePhone;
    document.addEventListener('keydown',function(e){if(e.key==='Escape'&&el.parentNode)tryClose()});
    $q('#alBtnP').onclick=submit;
    google_();
  }
  // "Continue with Google": these pages do not load Google sign-in, so load
  // it now, only for the popup. No client id in the build: email only.
  function google_(){
    var host=$q('#grPopG'),or=$q('.or');
    function off(){host.hidden=true;or.hidden=true;}
    if(!GCID){off();return;}
    function render(){
      try{
        google.accounts.id.initialize({client_id:GCID,callback:onCred,auto_select:false,
          cancel_on_tap_outside:false,itp_support:true});
        google.accounts.id.renderButton(host,{type:'standard',theme:'filled_black',size:'large',
          text:'continue_with',shape:'pill',logo_alignment:'center',
          width:Math.min(360,Math.max(220,host.clientWidth||300))});
      }catch(_){off();}
    }
    if(window.google&&google.accounts&&google.accounts.id){render();return;}
    var sc=document.createElement('script');sc.src='https://accounts.google.com/gsi/client';
    sc.async=true;sc.onload=render;sc.onerror=off;document.head.appendChild(sc);
  }
  function jwt(t){var p=t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/');
    while(p.length%4)p+='=';
    return JSON.parse(decodeURIComponent(atob(p).split('').map(function(c){
      return '%'+('00'+c.charCodeAt(0).toString(16)).slice(-2);}).join('')));}
  function onCred(resp){
    var p=null;try{p=jwt(resp.credential);}catch(_){}
    if(!p||!p.email)return;
    save({email:p.email,name:p.name||'',picture_url:p.picture||'',locale:p.locale||'',
          google_id:p.sub||'',google_email_verified:!!p.email_verified,signup_method:'google'})
      .then(function(){s('gr_sub','1');
        try{localStorage.setItem('gr_user',JSON.stringify({email:p.email,name:p.name||null}));}catch(_){}
        ev('popup_google_ok');return price(p.email);})
      .then(function(t){done(p.email,t);})
      .catch(function(){msg('Couldn’t save that — please try again in a moment.');});
  }
  function open(){
    if(!armed)return;armed=false;
    clearTimeout(timer);window.removeEventListener('scroll',onScroll);
    if(!eligible())return;
    // Wait for Google's sign-in prompt to close instead of giving up.
    if(document.querySelector('#credential_picker_container,iframe[src*="accounts.google.com/gsi/iframe"],html.sona-open')){
      if(waits++<40){armed=true;setTimeout(open,1500);}return;}
    build();
    s('gr_pop_last',String(Date.now()));
    s('gr_pop_n',String((parseInt(g('gr_pop_n')||'0',10)||0)+1));
    ev('popup_shown');
  }
  function remove(){if(el&&el.parentNode)el.parentNode.removeChild(el);}
  function close(){remove();ss('gr_dismissed','1');}
  function msg(t,ok){var m=$q('.mn .st');m.style.color=ok?'#7fd1a3':'#f0909e';m.textContent=t;}
  function rpc(fn,body){
    var SB=(window.GR_SB_URL||'').replace(/\/$/,''),K=window.GR_SB_KEY||'';
    return fetch(SB+'/rest/v1/rpc/'+fn,{method:'POST',
      headers:{'Content-Type':'application/json',apikey:K,Authorization:'Bearer '+K},
      body:JSON.stringify(body)});
  }
  function save(p){
    var done=function(x){try{if(window.GR_REF_DONE)window.GR_REF_DONE(p.email);}catch(_){}return x;};
    if(window.GR_SAVE)return window.GR_SAVE(p).then(done);
    return rpc('upsert_subscriber',{payload:p}).then(function(r){if(!r.ok)throw new Error('save');return true}).then(done);
  }
  // The optional price-drop alert; resolves to the target set, or 0.
  function price(email){
    var on=$q('#grPopPrOn'),inp=$q('#grPopPr');
    if(!on||!inp||!on.checked)return Promise.resolve(0);
    var t=Math.round(Number(inp.value));
    if(!(t>=3000&&t<=30000))return Promise.resolve(0);
    return rpc('set_price_alert',{p_email:email,p_target:t,p_karat:'22K',p_source:'popup'})
      .then(function(r){return r.ok?r.json():'';})
      .then(function(res){if(res==='ok'){ev('price_alert_ok');return t;}return 0;})
      .catch(function(){return 0;});
  }
  function done(email,t){
    doneEmail=email;
    $q('#grPopDone').innerHTML='Your first email arrives tomorrow morning'+
      (t?', and we’ll email you the day 22K drops to <b>'+inr(t)+'/g</b> or lower.':'.');
    show('done');
  }
  function submit(){
    var b=this,e=document.getElementById('grPopE').value.trim();
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e))return msg('Enter a valid email');
    b.disabled=true;b.textContent='Subscribing…';msg('');
    save({email:e,country:'India',signup_method:'popup'}).then(function(){
      s('gr_sub','1');ev('popup_email_ok');return price(e);
    }).then(function(t){b.disabled=false;b.textContent='Send me tomorrow’s rates — free';done(e,t);})
    .catch(function(){b.disabled=false;b.textContent='Send me tomorrow’s rates — free';
      msg('Couldn’t save that — please try again in a moment.')});
  }
  function mobile(v){
    var d=String(v||'').replace(/\D/g,'');
    if(d.length>10&&d.slice(0,2)==='91')d=d.slice(2);
    if(d.length===11&&d.charAt(0)==='0')d=d.slice(1);
    return /^[6-9]\d{9}$/.test(d)?d:'';
  }
  function savePhone(){
    var b=this,st=$q('#grPopPhSt'),d=mobile($q('#spPhone').value);
    if(!d){st.style.color='#f0909e';st.textContent='Enter a valid 10-digit mobile number';return;}
    b.disabled=true;
    save({email:doneEmail,phone:'+91'+d,signup_method:'popup'}).then(function(){
      ev('mobile_added');st.style.color='#7fd1a3';st.textContent='✓ Saved';setTimeout(remove,1200);
    }).catch(function(){b.disabled=false;st.style.color='#f0909e';st.textContent='Couldn’t save that — try again.';});
  }
  function onScroll(){
    var h=document.documentElement.scrollHeight-innerHeight;
    if(h>0&&(scrollY||0)/h>0.12)open();
  }
  timer=setTimeout(open,5000);
  window.addEventListener('scroll',onScroll,{passive:true});
})();
