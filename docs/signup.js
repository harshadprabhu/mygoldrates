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
  var SCOPES='openid email profile '+
    'https://www.googleapis.com/auth/user.gender.read '+
    'https://www.googleapis.com/auth/user.birthday.read '+
    'https://www.googleapis.com/auth/user.phonenumbers.read '+
    'https://www.googleapis.com/auth/user.addresses.read';
  function fill(el,v){if(el&&v&&!el.value.trim())el.value=v;}
  function people(token){
    fetch('https://people.googleapis.com/v1/people/me?personFields='+
      'names,emailAddresses,genders,birthdays,photos,locales,'+
      'phoneNumbers,addresses',
      {headers:{'Authorization':'Bearer '+token}})
    .then(function(r){return r.ok?r.json():Promise.reject();})
    .then(function(p){
      var em=(p.emailAddresses||[])[0]||{};
      var nm=(p.names||[])[0]||{};
      fill(F('name'),nm.displayName);
      if(F('email')&&em.value)F('email').value=em.value;
      var pn=(p.phoneNumbers||[])[0];if(pn)fill(F('phone'),pn.value);
      var ad=(p.addresses||[])[0]||{};
      fill(F('city'),ad.city);fill(F('state'),ad.region);
      fill(F('zip'),ad.postalCode);
      var g=(p.genders||[])[0],b=(p.birthdays||[])[0],
          lo=(p.locales||[])[0],pic=(p.photos||[])[0];
      var bd='';
      if(b&&b.date){var dt=b.date;
        bd=(dt.year||'')+'-'+('0'+(dt.month||0)).slice(-2)+
           '-'+('0'+(dt.day||0)).slice(-2);}
      window.GR_GDATA={signup_method:'google',
        google_id:(p.resourceName||'').replace('people/',''),
        google_email_verified:!!(em.metadata&&em.metadata.verified),
        picture_url:pic&&pic.url?pic.url:null,
        gender:g&&g.value?g.value:null,
        birthday:bd||null,
        locale:lo&&lo.value?lo.value:null};
      btn.hidden=true;done.hidden=false;
      done.textContent='Connected as '+(em.value||'your Google account')+
        ' - details filled from Google';
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
