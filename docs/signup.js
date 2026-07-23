(function(){
  var GCID=window.GR_GCID||'',
      SB=window.GR_SB_URL||'', KEY=window.GR_SB_KEY||'';
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
  function pinLookup(){
    if(!zip)return;var v=(zip.value||'').trim();
    if(!/^[1-9]\d{5}$/.test(v))return;
    var c=F('country');if(c&&c.value&&c.value!=='India')return;
    fetch('https://api.postalpincode.in/pincode/'+v)
      .then(function(r){return r.json();})
      .then(function(j){var d=j&&j[0];
        if(!d||d.Status!=='Success'||!d.PostOffice||!d.PostOffice.length)return;
        var po=d.PostOffice;if(c)c.value='India';
        if(F('state')&&!F('state').value.trim())F('state').value=po[0].State;
        if(F('city')&&!F('city').value.trim())F('city').value=po[0].District;
        if(area){var dl=document.getElementById(area.getAttribute('list'));
          if(dl){dl.innerHTML='';po.forEach(function(p){var o=
            document.createElement('option');o.value=p.Name;dl.appendChild(o);});}
          if(!area.value.trim())area.value=po[0].Name;}
      }).catch(function(){});
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
  }

  /* ---- optional Google One Tap, SITE-WIDE (popup only, no buttons) ----
     The One Tap prompt appears on its own; when the user picks an account we
     silently capture + save their Google data and show a small header chip.
     No persistent "Sign in with Google" button anywhere. */
  if(!GCID)return;
  function decode(jwt){try{return JSON.parse(decodeURIComponent(
    atob(jwt.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')).split('')
      .map(function(c){return '%'+('00'+c.charCodeAt(0).toString(16)).slice(-2);})
      .join('')));}catch(e){return null;}}
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
  function onCred(resp){
    var p=resp&&resp.credential?decode(resp.credential):null;
    if(!p||!p.email)return;
    var g={signup_method:'google',email:p.email,name:p.name||null,
      google_id:p.sub||null,google_email_verified:!!p.email_verified,
      picture_url:p.picture||null,locale:p.locale||null};
    window.GR_GDATA=g;
    try{localStorage.setItem('gr_user',JSON.stringify(
      {email:p.email,name:p.name,picture:p.picture}));}catch(e){}
    chip({email:p.email,name:p.name,picture:p.picture});
    saveSubscriber(g).catch(function(){});   /* grab + save Google data at once */
    prefill({email:p.email,name:p.name});
  }
  var tries=0;
  (function gready(){
    if(window.google&&google.accounts&&google.accounts.id){
      google.accounts.id.initialize({client_id:GCID,callback:onCred,
        auto_select:true,cancel_on_tap_outside:true,itp_support:true});
      if(!(stored&&stored.email))
        try{google.accounts.id.prompt();}catch(e){}   /* One Tap: comes & goes */
    }else if(tries++<40){setTimeout(gready,150);}
  })();
})();
