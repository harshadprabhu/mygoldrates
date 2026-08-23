(function(){
  var SB=window.GR_SB_URL||'', KEY=window.GR_SB_KEY||'';
  var form=document.getElementById('m-form')||document.getElementById('inq');
  function F(n){return form?form.elements[n]:null;}

  /* ---- save OR merge a subscriber, keyed by email ----
     Uses the upsert_subscriber RPC (merges into the same email row); if the
     RPC isn't deployed yet it falls back to a plain insert of base fields. */
  function saveSubscriber(payload){
    if(!SB||!KEY||!payload||!payload.email)return Promise.reject('cfg');
    return fetch(SB+'/rest/v1/rpc/upsert_subscriber',{method:'POST',
      headers:{'Content-Type':'application/json','apikey':KEY,
               'Authorization':'Bearer '+KEY},
      body:JSON.stringify({payload:payload})
    }).then(function(r){
      if(r.ok)return true;
      var base={};['name','email','phone','country','state','city','zip',
        'area','offers_optin'].forEach(function(k){
          if(payload[k]!==undefined)base[k]=payload[k];});
      return fetch(SB+'/rest/v1/inquiries',{method:'POST',
        headers:{'Content-Type':'application/json','apikey':KEY,
                 'Authorization':'Bearer '+KEY,'Prefer':'return=minimal'},
        body:JSON.stringify(base)}).then(function(r2){
          if(!r2.ok)throw new Error('save');return true;});
    });
  }
  window.GR_SAVE=saveSubscriber;

  /* ---- form conveniences: +91 phone default, PIN -> area/city/state ---- */
  var zip=F('zip'),area=F('area');
  /* India Post PO names carry a "S.O"/"B.O"/"H.O" suffix - strip it for a
     clean neighbourhood name (e.g. "Kalachowki S.O" -> "Kalachowki"). */
  function cleanPO(n){return (n||'').replace(/\s+(S\.?O\.?|B\.?O\.?|H\.?O\.?)$/i,'').trim();}
  function pinLookup(force,preferArea){
    if(!zip)return;var v=(zip.value||'').trim();
    if(!/^[1-9]\d{5}$/.test(v))return;
    var c=F('country');if(c&&c.value&&c.value!=='India')return;
    fetch('https://api.postalpincode.in/pincode/'+v)
      .then(function(r){return r.json();})
      .then(function(j){var d=j&&j[0];
        if(!d||d.Status!=='Success'||!d.PostOffice||!d.PostOffice.length)return;
        var po=d.PostOffice;if(c)c.value='India';
        var district=po[0].District||'';
        if(F('state')&&(force||!F('state').value.trim()))F('state').value=po[0].State;
        if(F('city')&&(force||!F('city').value.trim()))F('city').value=district;
        if(!area)return;
        /* Offer every locality in this PIN in the dropdown - one PIN covers
           several areas, so the user picks their exact one. */
        var names=[];po.forEach(function(p){var n=cleanPO(p.Name);
          if(n&&names.indexOf(n)<0)names.push(n);});
        var dl=document.getElementById(area.getAttribute('list'));
        if(dl){dl.innerHTML='';names.forEach(function(n){
          var o=document.createElement('option');o.value=n;dl.appendChild(o);});}
        if(!force&&area.value.trim())return;
        var pick='';
        if(preferArea){        /* match the GPS neighbourhood to a PO name */
          var pl=preferArea.toLowerCase();
          for(var i=0;i<names.length;i++){var nl=names[i].toLowerCase();
            if(nl===pl||nl.indexOf(pl)>=0||pl.indexOf(nl)>=0){pick=names[i];break;}}
          if(!pick)pick=preferArea;
        }
        if(!pick){           /* else first locality that isn't just the city */
          for(var k=0;k<names.length;k++){
            if(names[k].toLowerCase()!==district.toLowerCase()){pick=names[k];break;}}
        }
        if(!pick)pick=names[0]||'';
        if(pick)area.value=pick;
      }).catch(function(){});
  }
  /* ---- "use my location": geolocation -> reverse geocode -> address ---- */
  function set(n,v,force){var el=F(n);
    if(el&&v&&(force||!el.value.trim()))el.value=v;}
  function useLocation(btn){
    if(!navigator.geolocation){alert('Location is not supported by this '+
      'browser - please type your address.');return;}
    var old=btn.textContent;btn.disabled=true;btn.textContent='Locating...';
    function restore(){btn.disabled=false;btn.textContent=old;}
    function jget(u){return fetch(u,{headers:{Accept:'application/json'}})
      .then(function(r){return r.ok?r.json():null;})
      .catch(function(){return null;});}
    navigator.geolocation.getCurrentPosition(function(pos){
      var la=pos.coords.latitude,lo=pos.coords.longitude;
      /* OpenStreetMap/Nominatim first: it reliably returns the Indian PIN
         code and a real neighbourhood name. BigDataCloud returns an empty
         postcode for most Indian coordinates and repeats the city as the
         locality - that's why the area used to come out as "Mumbai" twice
         with no PIN. It stays as a backup for state/city only. */
      Promise.all([
        jget('https://nominatim.openstreetmap.org/reverse?format=jsonv2'+
             '&zoom=18&addressdetails=1&lat='+la+'&lon='+lo),
        jget('https://api.bigdatacloud.net/data/reverse-geocode-client?'+
             'latitude='+la+'&longitude='+lo+'&localityLanguage=en')
      ]).then(function(res){
        var n=res[0],b=res[1];
        if(!n&&!b){restore();
          alert('Could not look up your location - please type your address.');
          return;}
        var a=(n&&n.address)||{};
        var city=a.city||a.town||a.municipality||a.village||
                 String(a.state_district||'').replace(/\s+district$/i,'')||
                 (b&&(b.city||b.locality))||'';
        var areaName=a.suburb||a.neighbourhood||a.quarter||a.city_district||'';
        var st=a.state||(b&&b.principalSubdivision)||'';
        var pin=String(a.postcode||(b&&b.postcode)||'').trim();
        var c=F('country');
        if(c&&/india/i.test(a.country||(b&&b.countryName)||''))c.value='India';
        set('state',st,true);
        set('city',city,true);
        if(pin)set('zip',pin,true);
        /* never echo the city straight back as the area */
        if(area&&areaName&&areaName.toLowerCase()!==String(city).toLowerCase())
          set('area',areaName,true);
        var v=(zip&&zip.value||'').trim();
        if(/^[1-9]\d{5}$/.test(v))pinLookup(true,areaName);
        btn.textContent='Location added';
        setTimeout(restore,2500);
      });
    },function(err){restore();
      alert(err&&err.code===1?'Location permission was denied. You can type '+
        'your address instead.':'Could not get your location - please type '+
        'your address.');},
     {enableHighAccuracy:true,timeout:12000,maximumAge:600000});
  }

  if(form){
    var ph=F('phone');
    if(ph){ph.addEventListener('focus',function(){
        if(!ph.value.trim())ph.value='+91 ';});
      ph.addEventListener('blur',function(){var v=ph.value.replace(/[^\d]/g,'');
        if(/^[6-9]\d{9}$/.test(v))ph.value='+91 '+v;});}
    if(zip){zip.addEventListener('input',function(){
        if(/^[1-9]\d{5}$/.test(zip.value.trim()))pinLookup();});
      zip.addEventListener('blur',pinLookup);}
    var lb=form.querySelector('.locbtn');
    if(lb)lb.addEventListener('click',function(){useLocation(lb);});
  }

  /* ---- header chip (shared markup) + sign-out, available on every page.
     Actual Google sign-in (auto One Tap + button) is owned by the gate
     modal's own script; this restores the visual state from localStorage
     so a returning user doesn't have to sign in again. ---- */
  function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function chipHTML(u){
    return '<span class="uchip" title="'+esc(u.email)+'">'+
      (u.picture?'<img src="'+esc(u.picture)+'" alt="" referrerpolicy="no-referrer">':'')+
      '<span>'+esc(u.name||u.email||'Signed in')+'</span></span>'+
      '<button type="button" class="signout-btn">Sign out</button>';
  }
  window.GR_CHIP_HTML=chipHTML;
  function chip(u){var h=document.getElementById('hauth');if(!h)return;
    h.hidden=false;h.innerHTML=chipHTML(u);}

  /* Sign out: clear our session, stop Google auto-selecting the same account
     next load, and clear Google's g_state cookie so the One Tap prompt is no
     longer in its "recently dismissed" cooldown. */
  function signOut(){
    try{localStorage.removeItem('gr_user');}catch(e){}
    try{localStorage.removeItem('gr_sub');}catch(e){}
    try{sessionStorage.removeItem('gr_dismissed');}catch(e){}
    try{if(window.google&&google.accounts&&google.accounts.id)
      google.accounts.id.disableAutoSelect();}catch(e){}
    document.cookie='g_state=;path=/;max-age=0';
    document.cookie='g_state=;path=/;domain=.'+location.hostname+';max-age=0';
    var h=document.getElementById('hauth');
    if(h){h.hidden=true;h.innerHTML='';}
    location.reload();
  }
  window.GR_SIGNOUT=signOut;
  document.addEventListener('click',function(e){
    var b=e.target&&e.target.closest?e.target.closest('.signout-btn'):null;
    if(b){e.preventDefault();signOut();}
  });

  function prefill(u){if(!form)return;
    if(F('email')&&!F('email').value.trim())F('email').value=u.email||'';
    if(F('name')&&!F('name').value.trim())F('name').value=u.name||'';
    if(F('phone')&&!F('phone').value.trim())F('phone').value='+91 ';}
  var stored=null;try{stored=JSON.parse(localStorage.getItem('gr_user')||'null');}
    catch(e){}
  if(stored&&stored.email){chip(stored);prefill(stored);}
})();

/* ---- pageview + click analytics, day-wise (Supabase page_views/click_events) ---- */
(function(){
  var SB=window.GR_SB_URL||'', KEY=window.GR_SB_KEY||'';
  if(!SB||!KEY)return;
  var SID;
  try{
    SID=localStorage.getItem('gr_sid');
    if(!SID){
      SID=(window.crypto&&crypto.randomUUID)?crypto.randomUUID():
        (Date.now().toString(36)+Math.random().toString(36).slice(2));
      localStorage.setItem('gr_sid',SID);
    }
  }catch(e){SID='';}
  function post(table,row,retried){
    fetch(SB+'/rest/v1/'+table,{method:'POST',
      headers:{'Content-Type':'application/json','apikey':KEY,
               'Authorization':'Bearer '+KEY,'Prefer':'return=minimal'},
      body:JSON.stringify(row)}).then(function(r){
        // A schema mismatch (e.g. a column added to the client before the
        // matching migration has actually been run against the live DB)
        // returns a normal, non-throwing HTTP error here - fetch() only
        // rejects on a network failure, so a bare .catch() alone silently
        // drops every single insert with no sign anything is wrong. Same
        // graceful-degradation shape as send()'s retry-without-newer-fields
        // above: if this looks like exactly that case, retry once with the
        // newer field stripped rather than losing the whole pageview.
        if(!r.ok&&!retried&&row.host!==undefined){
          var row2={};for(var k in row){if(k!=='host')row2[k]=row[k];}
          post(table,row2,true);
        }
      }).catch(function(){});
  }
  post('page_views',{page:location.pathname,referrer:document.referrer||null,
    session_id:SID,host:location.hostname});

  /* delegated click tracking on interactive elements, de-duped per target */
  var lastTarget=null,lastAt=0;
  document.addEventListener('click',function(e){
    var el=e.target&&e.target.closest?
      e.target.closest('a[href],button,input[type="submit"],[role="button"]'):null;
    if(!el)return;
    var label=el.id||el.getAttribute('data-track')||
      (el.textContent||'').trim().slice(0,60)||el.tagName.toLowerCase();
    if(!label)return;
    var now=Date.now();
    if(label===lastTarget&&now-lastAt<2000)return;
    lastTarget=label;lastAt=now;
    post('click_events',{page:location.pathname,target:label,session_id:SID});
  },true);
})();
