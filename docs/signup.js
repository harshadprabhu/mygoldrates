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

  /* ---- optional Google sign-in (ID token: profile is in the token) ---- */
  var GCID=window.GR_GCID||'';
  var wrap=document.getElementById('gwrap');
  if(!GCID||!wrap)return;
  wrap.hidden=false;
  form.classList.add('has-google');           /* CSS hides manual fields */
  var host=document.getElementById('ghost'),
      done=wrap.querySelector('.gdone'),
      manual=document.getElementById('m-manual')||
             document.getElementById('f-manual'),
      link=document.getElementById('gmanual');
  function fill(el,v){if(el&&v&&!el.value.trim())el.value=v;}
  function reveal(){
    if(manual)manual.classList.add('reveal');
    if(F('phone')&&!F('phone').value.trim())F('phone').value='+91 ';
  }
  if(link)link.addEventListener('click',function(e){
    e.preventDefault();reveal();link.style.display='none';});
  function decode(jwt){
    try{return JSON.parse(decodeURIComponent(
      atob(jwt.split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))
        .split('').map(function(c){
          return '%'+('00'+c.charCodeAt(0).toString(16)).slice(-2);})
        .join('')));}catch(e){return null;}
  }
  function onCred(resp){
    var p=resp&&resp.credential?decode(resp.credential):null;
    if(!p){reveal();if(link)link.style.display='none';return;}
    fill(F('name'),p.name);
    if(F('email')&&p.email)F('email').value=p.email;
    window.GR_GDATA={signup_method:'google',
      google_id:p.sub||null,
      google_email_verified:!!p.email_verified,
      picture_url:p.picture||null,
      locale:p.locale||null};
    if(done){done.hidden=false;
      done.textContent='Signed in as '+(p.email||'your Google account')+
        ' - add your phone below to finish.';}
    reveal();if(link)link.style.display='none';
    if(zip&&zip.value.trim())pinLookup();
  }
  var tries=0;
  (function gready(){
    if(window.google&&google.accounts&&google.accounts.id){
      google.accounts.id.initialize({client_id:GCID,callback:onCred,
        auto_select:false,cancel_on_tap_outside:true});
      google.accounts.id.renderButton(host,{type:'standard',
        theme:'filled_blue',size:'large',text:'continue_with',
        shape:'pill',logo_alignment:'center',
        width:Math.min(360,Math.max(240,host.clientWidth||300))});
    }else if(tries++<40){setTimeout(gready,150);}
    else if(link){reveal();link.style.display='none';}   /* GIS blocked */
  })();
})();
