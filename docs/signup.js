(function(){
  var form=document.getElementById('m-form')||document.getElementById('inq');
  if(!form)return;
  function F(n){return form.elements[n];}

  /* ---- phone: default to India +91 ---- */
  var ph=F('phone');
  if(ph){
    ph.addEventListener('focus',function(){
      if(!ph.value.trim())ph.value='+91 ';});
    ph.addEventListener('blur',function(){
      var v=ph.value.replace(/[^\d]/g,'');
      if(/^[6-9]\d{9}$/.test(v))ph.value='+91 '+v;   /* bare 10-digit Indian */
    });
  }

  /* ---- PIN code -> area/city/state/country (India Post data) ---- */
  var zip=F('zip'),area=F('area');
  function pinLookup(){
    var v=(zip.value||'').trim();
    if(!/^[1-9]\d{5}$/.test(v))return;
    var c=F('country');
    if(c&&c.value&&c.value!=='India')return;
    fetch('https://api.postalpincode.in/pincode/'+v)
      .then(function(r){return r.json();})
      .then(function(j){
        var d=j&&j[0];
        if(!d||d.Status!=='Success'||!d.PostOffice||!d.PostOffice.length)return;
        var po=d.PostOffice;
        if(c)c.value='India';
        if(F('state')&&!F('state').value.trim())F('state').value=po[0].State;
        if(F('city')&&!F('city').value.trim())F('city').value=po[0].District;
        if(area){
          var dl=document.getElementById(area.getAttribute('list'));
          if(dl){dl.innerHTML='';po.forEach(function(p){
            var o=document.createElement('option');o.value=p.Name;
            dl.appendChild(o);});}
          if(!area.value.trim())area.value=po[0].Name;
        }
      }).catch(function(){});
  }
  if(zip){
    zip.addEventListener('input',function(){
      if(/^[1-9]\d{5}$/.test(zip.value.trim()))pinLookup();});
    zip.addEventListener('blur',pinLookup);
  }

  /* ---- optional Google sign-in (People API autofill) ---- */
  var GCID=window.GR_GCID||'';
  var wrap=document.getElementById('gwrap');
  if(!GCID||!wrap)return;
  wrap.hidden=false;
  var btn=wrap.querySelector('.gbtn'),done=wrap.querySelector('.gdone');
  /* Basic (non-sensitive) scopes only - no app verification needed. Gender/
     birthday/address can be added back once the app is Google-verified. */
  var SCOPES='openid email profile';
  function fill(el,v){if(el&&v&&!el.value.trim())el.value=v;}
  function people(token){
    /* Standard OIDC userinfo - works with basic scopes, no People API. */
    fetch('https://www.googleapis.com/oauth2/v3/userinfo',
      {headers:{'Authorization':'Bearer '+token}})
    .then(function(r){return r.ok?r.json():Promise.reject();})
    .then(function(u){
      fill(F('name'),u.name);
      if(F('email')&&u.email)F('email').value=u.email;
      window.GR_GDATA={signup_method:'google',
        google_id:u.sub||null,
        google_email_verified:!!u.email_verified,
        picture_url:u.picture||null,
        locale:u.locale||null};
      btn.hidden=true;done.hidden=false;
      done.textContent='Connected as '+(u.email||'your Google account')+
        ' - name and email filled from Google';
      if(zip&&zip.value.trim())pinLookup();
    }).catch(function(){
      alert('Could not fetch details from Google - please fill the form '+
            'manually.');});
  }
  var tc=null;
  btn.addEventListener('click',function(){
    if(!(window.google&&google.accounts&&google.accounts.oauth2)){
      alert('Google sign-in is still loading - try again in a second.');
      return;}
    tc=tc||google.accounts.oauth2.initTokenClient({client_id:GCID,
      scope:SCOPES,
      callback:function(res){
        if(res&&res.access_token)people(res.access_token);}});
    tc.requestAccessToken();
  });
})();
