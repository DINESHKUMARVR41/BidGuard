const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let allTenders=[];
function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function toast(msg,type=""){const e=$("#toast");e.textContent=msg;e.className="toast "+(type==="error"?"error":type==="info"?"info":"");window.scrollTo({top:0,behavior:"smooth"});setTimeout(()=>e.classList.add("hidden"),7000);}
const firebaseAppModule = await import("https://www.gstatic.com/firebasejs/11.0.2/firebase-app.js");
const firebaseAuthModule = await import("https://www.gstatic.com/firebasejs/11.0.2/firebase-auth.js");
const configResponse = await fetch("/api/config");
const publicConfig = await configResponse.json();
const firebaseConfig = publicConfig.firebase || {};
let firebaseAuth = null;
let firebaseReady = false;
try {
  if (!firebaseConfig.apiKey || !firebaseConfig.projectId || !firebaseConfig.appId || !firebaseConfig.authDomain) {
    throw new Error("Firebase web config is incomplete. Fill FIREBASE_API_KEY, FIREBASE_AUTH_DOMAIN, FIREBASE_PROJECT_ID and FIREBASE_APP_ID in .env, then restart BidGuard.");
  }
  const firebaseApp = firebaseAppModule.initializeApp(firebaseConfig);
  firebaseAuth = firebaseAuthModule.getAuth(firebaseApp);
  firebaseReady = true;
} catch (e) {
  console.error(e);
  setTimeout(() => authError(e.message || "Firebase initialization failed."), 0);
}
async function api(url,opts={}){
  const headers = new Headers(opts.headers || {});
  if (firebaseAuth?.currentUser) headers.set("Authorization", `Bearer ${await firebaseAuth.currentUser.getIdToken()}`);
  const r=await fetch(url,{credentials:"same-origin",...opts,headers});let d={};try{d=await r.json()}catch{}if(!r.ok)throw Error(d.detail||d.message||`HTTP ${r.status}`);return d;
}
function friendlyAuthError(error){
  const code=error?.code||"";
  const messages={
    "auth/invalid-credential":"Incorrect email or password.",
    "auth/invalid-email":"Enter a valid email address.",
    "auth/email-already-in-use":"An account with this email already exists.",
    "auth/weak-password":"Choose a stronger password (at least 6 characters; BidGuard asks for 8).",
    "auth/user-disabled":"This account has been disabled.",
    "auth/too-many-requests":"Too many attempts. Wait a while and try again.",
    "auth/network-request-failed":"Network error. Check your internet connection.",
    "auth/operation-not-allowed":"Enable Email/Password sign-in in Firebase Console > Authentication > Sign-in method."
  };
  return messages[code] || error?.message || "Firebase authentication failed.";
}
function go(v){$$(".view").forEach(x=>x.classList.add("hidden"));$(`#view-${v}`).classList.remove("hidden");$$(".nav").forEach(x=>x.classList.toggle("active",x.dataset.view===v));$("#page-title").textContent=({dashboard:"Dashboard",tenders:"Discover tenders",company:"Company profile",detail:"Tender analysis"})[v]||"BidGuard";if(v==="dashboard"||v==="tenders")refresh();}
function statusClass(s){return s==="Appears satisfied"?"good":s==="Potential mismatch"?"bad":["Missing evidence","Needs manual verification"].includes(s)?"warn":"";}
function card(t){let fs=t.analysis?.findings||[],risks=fs.filter(f=>["Potential mismatch","Missing evidence","Needs manual verification"].includes(f.status)).length;return `<article class="tender"><div><h3 data-open="${t.id}">${esc(t.title)}</h3><div class="meta"><span>${esc(t.authority||"Authority not listed")}</span><span>${esc(t.location||"Location not listed")}</span><span>Deadline: ${esc(t.closing_date||"not verified")}</span></div><div class="meta"><span>Source: ${esc(t.source_name)}</span><span>Retrieved: ${esc((t.retrieved_at||"").slice(0,10))}</span><span>Profile match: ${Number(t.match_score||0)}%</span></div>${(t.match_reasons||[]).length?`<div class="meta"><span>${esc(t.match_reasons.slice(0,2).join(" · "))}</span></div>`:""}</div><div class="right"><span class="pill ${t.status==="analyzed"?(risks?"warn":"good"):""}">${t.status==="analyzed"?(risks?risks+" item(s) to review":"Analyzed"):"Not analyzed"}</span><button class="mini" data-open="${t.id}">View analysis →</button></div></article>`;}
async function refresh(){try{let q=$("#search")&&$("#view-tenders").classList.contains("hidden")===false?$("#search").value:"",s=$("#status-filter")&&!$("#view-tenders").classList.contains("hidden")?$("#status-filter").value:"all";let d=await api(`/api/tenders?q=${encodeURIComponent(q)}&status=${s}`);allTenders=d.tenders||[];$("#metric-total").textContent=d.count;$("#metric-analyzed").textContent=allTenders.filter(t=>t.status==="analyzed").length;$("#metric-review").textContent=allTenders.reduce((n,t)=>n+(t.analysis?.findings||[]).filter(f=>["Potential mismatch","Missing evidence","Needs manual verification"].includes(f.status)).length,0);$("#recent-list").innerHTML=allTenders.slice(0,4).map(card).join("");$("#tender-list").innerHTML=allTenders.map(card).join("");$("#empty").classList.toggle("hidden",allTenders.length>0);}catch(e){toast(e.message,"error");}}
async function loadCompany(){try{let d=await api("/api/company"),p=d.profile||{},f=$("#company-form");Object.entries(p).forEach(([k,v])=>{let el=f.elements.namedItem(k);if(el)el.value=v??""});let n=["company_name","industry","products_services","location"].filter(k=>String(p[k]||"").trim()).length;$("#metric-profile").textContent=n>=3?"Ready":"Incomplete";$("#profile-sub").textContent=`${n}/4 core details`;$("#profile-updated").textContent=d.updated_at?"Last saved "+new Date(d.updated_at).toLocaleString():"Profile not saved yet";}catch(e){toast(e.message,"error");}}
let activeDiscoveryPoll=null;
async function pollDiscovery(jobId){if(activeDiscoveryPoll===jobId)return;activeDiscoveryPoll=jobId;const statusEl=$("#discovery-status");try{while(true){const d=await api(`/api/discovery/jobs/${encodeURIComponent(jobId)}`);if(statusEl)statusEl.textContent=d.status==="running"?`Discovery is running in the background. Started ${new Date(d.started_at).toLocaleTimeString()}. You can keep using the app.`:`Last run: ${d.status} · ${d.message||""}`;if(d.status!=="running"){toast(`${d.message||"Discovery finished."} New tenders: ${d.imported||0}; duplicates: ${d.duplicates||0}.`,d.result_status==="success"?"":"info");await refresh();break;}await new Promise(resolve=>setTimeout(resolve,2500));}}catch(e){if(statusEl)statusEl.textContent=`Could not check discovery status: ${e.message}`;}finally{activeDiscoveryPoll=null;}}
async function discover(force=false){let bs=force?[$("#force-discover")]:[$("#discover-top"),$("#discover-main"),$("#hero-discover")].filter(Boolean);bs.forEach(b=>{b.disabled=true;b.dataset.old=b.textContent;b.textContent=force?"Starting refresh…":"Starting…"});const statusEl=$("#discovery-status");try{const d=await api(`/api/discovery/run${force?"?force=true":""}`,{method:"POST"});go("tenders");if(d.status==="cached"){if(statusEl)statusEl.textContent=`Cached result from ${d.finished_at||"the last run"}. Use Force refresh to search again.`;toast(`${d.message} Previously imported ${d.imported||0}; duplicates ${d.duplicates||0}.`,"info");await refresh();return;}if(d.job_id){if(statusEl)statusEl.textContent="Discovery started in the background. You can continue using BidGuard.";toast("Discovery started. This page will update when results arrive.","info");pollDiscovery(d.job_id);}else{toast(d.message||"Discovery could not start.","info");}}catch(e){toast(e.message,"error")}finally{bs.forEach(b=>{b.disabled=false;b.textContent=b.dataset.old|| (force?"Force refresh":"Discover tenders")})}}
function obj(form){let o={};for(let [k,v] of new FormData(form)){let el=form.elements.namedItem(k);o[k]=el&&el.type==="number"?(v===""?null:Number(v)):v;}return o;}
async function openTender(id){try{let t=await api(`/api/tenders/${id}`),a=t.analysis||{},fs=a.findings||[];let findings=fs.length?fs.map(f=>`<div class="finding"><div class="findinghead"><h4>${esc(f.category.replaceAll("_"," ").toUpperCase())}</h4><span class="pill ${statusClass(f.status)}">${esc(f.status)}</span></div><blockquote>${esc(f.requirement_text)}</blockquote><p><b>Why it matters:</b> ${esc(f.reason)}</p><p><b>Next action:</b> ${esc(f.recommended_action)}</p><p><b>Source:</b> ${esc(f.source)} · Page reference ${f.page||"unavailable"}</p></div>`).join(""):`<p>${t.raw_text?"No common requirement patterns detected. Review the document manually.":"No tender text extracted yet. Upload a text-based PDF or enter verified tender text."}</p>`;
$("#detail").innerHTML=`<div class="detailhead"><span class="pill">${esc(t.source_name)}</span><h2>${esc(t.title)}</h2><p>${esc(t.authority||"Authority not listed")} · ${esc(t.location||"Location not listed")}<br>Reference: ${esc(t.tender_reference||"not available")} · Deadline: ${esc(t.closing_date||"not verified")}<br><a href="${esc(t.source_url)}" target="_blank" rel="noopener noreferrer">Open official source ↗</a></p><button id="analyze" class="primary">Analyze eligibility</button> <button id="remove" class="outline">Remove tender</button></div><div class="detailgrid"><div><div class="detailpanel"><h3>Requirement-by-requirement review</h3>${findings}</div><div class="detailpanel"><h3>Extracted tender text</h3><pre>${esc((t.raw_text||"No text extracted yet.").slice(0,18000))}</pre></div></div><div><div class="detailpanel"><h3>Upload tender PDF</h3><div class="uploadbox"><input id="pdf" type="file" accept=".pdf,application/pdf"><p>Text-based PDF up to 15 MB. OCR for scanned PDFs is not included.</p><button id="upload" class="outline">Upload and extract</button></div></div><div class="detailpanel"><h3>Recommended next actions</h3><ul class="checklist">${(a.next_actions||["Upload a tender PDF or add verified tender text.","Check the official notice and corrigenda.","Verify requirements and evidence manually."]).map(x=>`<li>${esc(x)}</li>`).join("")}</ul></div><div class="detailpanel"><h3>Uploaded documents</h3>${(t.documents||[]).map(d=>`<p>${esc(d.filename)} · ${d.page_count} page(s)</p>`).join("")||"<p>No uploaded documents.</p>"}</div><div class="notice"><b>Preliminary analysis only</b><p>${esc((a.limitations||["This is not an official eligibility determination."])[0])}</p></div></div></div>`;
go("detail");
$("#analyze").onclick=async()=>{try{await api(`/api/tenders/${id}/analyze`,{method:"POST"});toast("Preliminary analysis completed.");await openTender(id)}catch(e){toast(e.message,"error")}};
$("#remove").onclick=async()=>{if(!confirm("Remove this tender and its uploaded documents?"))return;try{await api(`/api/tenders/${id}`,{method:"DELETE"});toast("Tender removed.");go("tenders")}catch(e){toast(e.message,"error")}};
$("#upload").onclick=async()=>{let file=$("#pdf").files[0];if(!file){toast("Choose a PDF first.","error");return}let fd=new FormData();fd.append("file",file);$("#upload").disabled=true;try{let r=await api(`/api/tenders/${id}/documents`,{method:"POST",body:fd});toast(`${r.message} Extracted ${r.characters_extracted} characters.`);await openTender(id)}catch(e){toast(e.message,"error")}finally{if($("#upload"))$("#upload").disabled=false}};
}catch(e){toast(e.message,"error")}}
$$(".nav").forEach(b=>b.onclick=()=>go(b.dataset.view));$$("[data-goto]").forEach(b=>b.onclick=()=>go(b.dataset.goto));$("#discover-top").onclick=()=>discover(false);$("#discover-main").onclick=()=>discover(false);$("#hero-discover").onclick=()=>discover(false);if($("#force-discover"))$("#force-discover").onclick=()=>discover(true);$("#toggle-manual").onclick=()=>$("#manual-form").classList.toggle("hidden");$("#back").onclick=()=>go("tenders");let searchTimer=null;$("#search").oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(refresh,180)};$("#status-filter").onchange=refresh;
$("#manual-form").onsubmit=async e=>{e.preventDefault();try{let r=await api("/api/tenders/manual",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(obj(e.target))});toast(r.status==="duplicate"?"Tender already saved.":"Tender saved.");e.target.reset();$("#manual-form").classList.add("hidden");await refresh()}catch(err){toast(err.message,"error")}};
$("#company-form").onsubmit=async e=>{e.preventDefault();try{await api("/api/company",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(obj(e.target))});toast("Company profile saved.");await loadCompany()}catch(err){toast(err.message,"error")}};
document.addEventListener("click",e=>{let b=e.target.closest("[data-open]");if(b)openTender(Number(b.dataset.open))});
function formObject(form){let o={};for(const [k,v] of new FormData(form)){const el=form.elements.namedItem(k);o[k]=el&&el.type==="number"?(v===""?null:Number(v)):v;}return o;}
function authError(msg){const e=$("#auth-error");e.textContent=msg;e.classList.remove("hidden");}
function showAuth(mode){$("#login-form").classList.toggle("hidden",mode!=="login");$("#register-form").classList.toggle("hidden",mode!=="register");$("#show-login").classList.toggle("active",mode==="login");$("#show-register").classList.toggle("active",mode==="register");$("#auth-error").classList.add("hidden");}
async function enterApp(user){$("#auth-screen").classList.add("hidden");$("#app-shell").classList.remove("hidden");$("#signed-in-as").textContent=user?.full_name||user?.email||"Workspace";await loadCompany();await refresh();go("dashboard");}
$("#show-login").onclick=()=>showAuth("login");$("#show-register").onclick=()=>showAuth("register");
$("#login-form").onsubmit=async e=>{
  e.preventDefault();const b=e.target.querySelector("button");b.disabled=true;
  try{
    if(!firebaseReady)throw new Error("Firebase is not configured. Check the Firebase values in .env and restart the server.");
    const values=formObject(e.target);
    await firebaseAuthModule.signInWithEmailAndPassword(firebaseAuth,values.email,values.password);
    const d=await api("/api/auth/me");e.target.reset();await enterApp(d.user);
  }catch(err){authError(friendlyAuthError(err))}finally{b.disabled=false}
};
$("#register-form").onsubmit=async e=>{
  e.preventDefault();const b=e.target.querySelector("button");b.disabled=true;
  try{
    if(!firebaseReady)throw new Error("Firebase is not configured. Check the Firebase values in .env and restart the server.");
    const values=formObject(e.target);
    const credential=await firebaseAuthModule.createUserWithEmailAndPassword(firebaseAuth,values.email,values.password);
    await firebaseAuthModule.updateProfile(credential.user,{displayName:values.full_name});
    const {email,password,...profile}=values;
    const d=await api("/api/auth/bootstrap",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(profile)});
    e.target.reset();await enterApp(d.user);toast("Firebase account created and company profile saved. Tender discovery is now personalized to your business.","info");
  }catch(err){authError(friendlyAuthError(err))}finally{b.disabled=false}
};
$("#logout").onclick=async()=>{try{await api("/api/auth/logout",{method:"POST"})}catch{}try{if(firebaseAuth?.currentUser)await firebaseAuthModule.signOut(firebaseAuth)}catch{}$("#app-shell").classList.add("hidden");$("#auth-screen").classList.remove("hidden");showAuth("login");};
if(firebaseReady){
  firebaseAuthModule.onAuthStateChanged(firebaseAuth,async user=>{
    if(!user){$("#auth-screen").classList.remove("hidden");$("#app-shell").classList.add("hidden");return;}
    try{const d=await api("/api/auth/me");await enterApp(d.user)}catch(err){authError(err.message);$("#auth-screen").classList.remove("hidden");$("#app-shell").classList.add("hidden");}
  });
} else {
  $("#auth-screen").classList.remove("hidden");$("#app-shell").classList.add("hidden");
}
