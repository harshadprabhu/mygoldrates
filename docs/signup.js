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
  function pinLookup(force){
    if(!zip)return;var v=(zip.value||'').trim();
    if(!/^[1-9]\d{5}$/.test(v))return;
    var c=F('country');if(c&&c.value&&c.value!=='India')return;
    fetch('https://api.postalpincode.in/pincode/'+v)
      .then(function(r){return r.json();})
      .then(function(j){var d=j&&j[0];
        if(!d||d.Status!=='Success'||!d.PostOffice||!d.PostOffice.length)return;
        var po=d.PostOffice;if(c)c.value='India';
        if(F('state')&&(force||!F('state').value.trim()))F('state').value=po[0].State;
        if(F('city')&&(force||!F('city').value.trim()))F('city').value=po[0].District;
        if(area){var dl=document.getElementById(area.getAttribute('list'));
          if(dl){dl.innerHTML='';po.forEach(function(p){var o=
            document.createElement('option');o.value=cleanPO(p.Name);dl.appendChild(o);});}
          if(force||!area.value.trim())area.value=cleanPO(po[0].Name);}
      }).catch(function(){});
  }
  /* ---- "use my location": geolocation -> reverse geocode -> address ---- */
  function set(n,v,force){var el=F(n);
    if(el&&v&&(force||!el.value.trim()))el.value=v;}
  function useLocation(btn){
    if(!navigator.geolocation){alert('Location is not supported by this '+
      'browser - please type your address.');return;}
    var old=btn.textContent;btn.disabled=true;btn.textContent='Locating...';
    navigator.geolocation.getCurrentPosition(function(pos){
      var la=pos.coords.latitude,lo=pos.coords.longitude;
      fetch('https://api.bigdatacloud.net/data/reverse-geocode-client?'+
        'latitude='+la+'&longitude='+lo+'&localityLanguage=en')
        .then(function(r){return r.json();})
        .then(function(d){
          var c=F('country');
          if(c&&d.countryName&&/india/i.test(d.countryName))c.value='India';
          set('state',d.principalSubdivision,true);
          set('city',d.city||d.locality,true);
          if(d.postcode)set('zip',d.postcode,true);
          btn.textContent='Location added';
          /* The PIN code lookup returns the actual local post-office name
             (e.g. "Kalachowki" for 400033) - far more precise for Indian
             addresses than the reverse-geocoded locality, so it wins over
             whatever BigDataCloud guessed and overwrites "area" once ready. */
          var v=(zip&&zip.value||'').trim();
          if(/^[1-9]\d{5}$/.test(v)){pinLookup(true);}
          else if(area){set('area',d.locality||d.city,true);}
          setTimeout(function(){btn.disabled=false;btn.textContent=old;},2500);
        }).catch(function(){btn.disabled=false;btn.textContent=old;
          alert('Could not look up your location - please type your address.');});
    },function(err){btn.disabled=false;btn.textContent=old;
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

  /* ---- restore header chip + prefill forms for a returning signed-in user.
     Actual Google sign-in (auto One Tap + button) is owned by the gate
     modal's own script (homepage only) - this just restores the visual
     state from localStorage so it doesn't require a fresh sign-in. ---- */
  function chip(u){var h=document.getElementById('hauth');if(!h)return;
    h.hidden=false;
    h.innerHTML='<span class="uchip" title="'+(u.email||'')+'">'+
      (u.picture?'<img src="'+u.picture+'" alt="" referrerpolicy="no-referrer">':'')+
      '<span>'+(u.name||u.email||'Signed in')+'</span></span>';}
  function prefill(u){if(!form)return;
    if(F('email')&&!F('email').value.trim())F('email').value=u.email||'';
    if(F('name')&&!F('name').value.trim())F('name').value=u.name||'';
    if(F('phone')&&!F('phone').value.trim())F('phone').value='+91 ';}
  var stored=null;try{stored=JSON.parse(localStorage.getItem('gr_user')||'null');}
    catch(e){}
  if(stored&&stored.email){chip(stored);prefill(stored);}
})();
