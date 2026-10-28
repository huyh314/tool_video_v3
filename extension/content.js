// Pure helpers remain callable in Node tests. All extraction is article-local.
function canonicalVideo_(href){
 try{
  const u=new URL(href,typeof window!=='undefined'&&window.location?window.location.href:'https://www.facebook.com/');
  if(u.protocol!=='https:'||!(u.hostname==='facebook.com'||u.hostname.endsWith('.facebook.com')))return null;
  let id,kind='watch';const reel=u.pathname.match(/\/reel\/(\d+)(?:\/|$)/),video=u.pathname.match(/\/videos\/(?:[^/]+\/)?(\d+)(?:\/|$)/);
  if(reel){id=reel[1];kind='reel';}else if(video)id=video[1];
  else if(/^\/(?:watch\/?|video\.php)$/.test(u.pathname)&&/^\d+$/.test(u.searchParams.get('v')||''))id=u.searchParams.get('v');
  else if(/^\d+$/.test(u.searchParams.get('story_fbid')||''))id=u.searchParams.get('story_fbid');
  else if(u.pathname.match(/\/posts\/(\d+)(?:\/|$)/))id=u.pathname.match(/\/posts\/(\d+)/)[1];
  // fbid identifies a post/photo, not necessarily the media ID: don't invent video IDs from it.
  if(!id)return null;
  return {post_id:'fb_'+id,video_id:id,post_url:kind==='reel'?'https://www.facebook.com/reel/'+id+'/':'https://www.facebook.com/watch/?v='+id};
 }catch{return null;}
}
function parseCount_(value){
 const s=String(value||'').trim().toLowerCase().replace(/\u00a0/g,' ');
 const m=s.match(/^(\d[\d.,]*)(?:\s*)(k|m|b|nghìn|ngàn|triệu|tỷ)?$/i);if(!m)return null;
 const unit=m[2],factor=unit?({k:1e3,m:1e6,b:1e9,'nghìn':1e3,'ngàn':1e3,'triệu':1e6,'tỷ':1e9}[unit]):1;
 let number=m[1];
 if(unit)number=number.replace(',','.');
 else if(/^\d{1,3}([.,]\d{3})+$/.test(number))number=number.replace(/[.,]/g,'');
 else if(/[.,]/.test(number))return null;
 const n=Number(number);return Number.isFinite(n)?Math.round(n*factor):null;
}
function publishedAt_(article){
 const time=article.querySelector('time[datetime],abbr[data-utime],[data-utime]');
 if(!time)return null;
 const raw=time.getAttribute('datetime')||time.getAttribute('data-utime');
 const date=/^\d+$/.test(raw||'')?new Date(Number(raw)*1000):new Date(raw);
 return Number.isFinite(date.getTime())?date.toISOString():null;
}
function metrics_(article){
 const values={likes:null,comments:null,shares:null};
 for(const element of article.querySelectorAll('[aria-label]')){
  const text=(element.getAttribute('aria-label')||'').trim().toLowerCase();
  const key=/bình luận|comments?/.test(text)?'comments':/chia sẻ|shares?/.test(text)?'shares':/lượt thích|likes?|cảm xúc|reactions?/.test(text)?'likes':null;
  if(!key||values[key]!==null)continue;
  const match=text.match(/(\d[\d.,]*\s*(?:nghìn|ngàn|triệu|tỷ|[kmb])?)/i);
  if(match)values[key]=parseCount_(match[1].trim());
 }
 return values;
}
function caption_(article){
 const specific=article.querySelector('[data-ad-preview="message"],[data-ad-comet-preview="message"]');
 if(specific)return specific.innerText.trim().slice(0,20000);
 const texts=[];
 for(const el of article.querySelectorAll('[dir="auto"]')){
  if(el.querySelector('[dir="auto"]'))continue;
  const t=el.innerText.trim();
  if(t.length<4||/^(Thích|Bình luận|Chia sẻ|Theo dõi|Like|Comment|Share|Follow)$/i.test(t)||texts.includes(t))continue;
  texts.push(t);
 }return texts.join('\n').slice(0,20000);
}
function isIgnoredLink_(el){
 try{
  return Boolean(el.closest('[role="navigation"], [role="banner"], [aria-label*="Thông báo" i], [aria-label*="Notifications" i], [data-pagelet*="ChatTab"], [data-pagelet*="Messaging"], [data-pagelet*="LeftRail"], [data-pagelet*="RightRail"]'));
 }catch{return false;}
}
function updateOverlay_(job, count, max, statusText){
 if(typeof document==='undefined')return;
 try{
  let el=document.getElementById('__fb_studio_v3_overlay');
  if(!el){
   el=document.createElement('div');
   el.id='__fb_studio_v3_overlay';
   el.style.cssText='position:fixed;top:16px;right:16px;z-index:999999999;background:#0d1117;color:#f0f6fc;padding:14px 18px;border-radius:12px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;font-size:13px;box-shadow:0 12px 32px rgba(0,0,0,0.65);border:1.5px solid #38bdf8;min-width:280px;pointer-events:none;line-height:1.4;';
   document.body.appendChild(el);
  }
  const name=String(job.channel?.name||'Facebook Reels').replace(/</g,'&lt;');
  const desc=String(statusText||'').replace(/</g,'&lt;');
  el.innerHTML=`
   <div style="display:flex;align-items:center;gap:8px;font-weight:700;color:#38bdf8;margin-bottom:6px;">
    <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#10b981;"></span>
    FB Auto Video Studio v3
   </div>
   <div style="font-size:12px;color:#94a3b8;margin-bottom:4px;">Kênh: <b style="color:#ffffff;">${name}</b></div>
   <div style="font-size:13px;color:#f1f5f9;margin-bottom:6px;">Tiến độ: <b style="color:#fbbf24;font-size:14px;">${count} / ${max} video</b></div>
   <div style="font-size:11px;color:#cbd5e1;background:rgba(255,255,255,0.08);padding:5px 8px;border-radius:6px;margin-bottom:6px;">${desc}</div>
   <div style="font-size:11px;color:#f87171;font-weight:600;">⚠️ Xin vui lòng KHÔNG đóng tab này trong khi quét.</div>
  `;
 }catch{}
}
function collectPosts_(job,map){
 let unknownDates=0;
 const articles=document.querySelectorAll('[role="main"] [role="article"],div[data-pagelet*="Reels"],div[data-pagelet*="Tahoe"]');
 for(const article of articles){
  if(isIgnoredLink_(article))continue;
  const refs=[...article.querySelectorAll('a[href]')].filter(a=>!isIgnoredLink_(a)).map(a=>canonicalVideo_(a.href)).filter(Boolean);
  const unique=new Map(refs.map(r=>[r.video_id,r]));
  // Containers covering several videos cannot safely associate caption/media with one ID.
  if(unique.size!==1)continue;
  const p=[...unique.values()][0],published=publishedAt_(article);
  if(published&&Date.now()-Date.parse(published)>Number(job.channel.scope_days||7)*86400000)continue;
  if(!published)unknownDates++;
  const old=map.get(p.post_id);
  const post={...p,channel_id:job.channel_id,caption:caption_(article),published_at:published,collected_at:new Date().toISOString(),...metrics_(article)};
  // Only use a direct HTTP URL from exactly one video in this same unambiguous article.
  const media=article.querySelectorAll('video');
  if(media.length===1){
   const src=media[0].currentSrc||media[0].src;
   try{const u=new URL(src);if(u.protocol==='https:'&&(u.hostname.endsWith('.fbcdn.net')||u.hostname.endsWith('.facebook.com')))post.direct_video_url=src;}catch{}
  }
  if(!old||post.caption.length>old.caption.length)map.set(p.post_id,post);
 }
 // Reels grids often have no article wrappers. Keep the explicit video identity,
 // but leave unavailable caption/date/metrics empty instead of borrowing another card.
 for(const link of document.querySelectorAll('a[href*="/reel/"],a[href*="/videos/"],a[href*="/watch"],a[href*="video.php"],a[href*="story_fbid"],a[href*="/posts/"]')){
  if(isIgnoredLink_(link))continue;
  const p=canonicalVideo_(link.href);if(!p||map.has(p.post_id))continue;
  const article=link.closest('[role="main"] [role="article"],div[data-pagelet*="Reels"],div[data-pagelet*="Tahoe"]');
  const published=article?publishedAt_(article):null;
  if(published&&Date.now()-Date.parse(published)>Number(job.channel.scope_days||7)*86400000)continue;
  const label=link.innerText?.trim()||link.getAttribute('aria-label')||'';
  map.set(p.post_id,{...p,channel_id:job.channel_id,caption:label.slice(0,20000),published_at:published,collected_at:new Date().toISOString(),likes:null,comments:null,shares:null});
  if(!published)unknownDates++;
 }
 return unknownDates;
}
function sleep_(ms){return new Promise(r=>setTimeout(r,ms));}
async function scan_(job){
 const map=new Map(),max=Math.max(1,Math.min(100,Number(job.channel.max_posts)||10));
 let stable=0,previousHeight=0,reachedEnd=false,unknown=false;
 updateOverlay_(job, 0, max, 'Đang mở trang và kiểm tra video...');
 for(let step=0;step<25;step++){
  if(document.querySelector('input[name="email"],input[name="pass"]')&&/login/i.test(window.location.href))throw new Error('Cần đăng nhập Facebook trong Chrome.');
  if(collectPosts_(job,map))unknown=true;
  updateOverlay_(job, map.size, max, `Đang cuộn tải thêm (bước ${step+1}/25)...`);
  if(map.size>=max)break;
  const height=document.documentElement.scrollHeight;
  stable=height===previousHeight?stable+1:0;previousHeight=height;
  if(stable>=4&&window.scrollY+window.innerHeight>=height-200){reachedEnd=true;break;}
  window.scrollBy({top:Math.max(650,window.innerHeight*.8),behavior:'instant'});
  await sleep_(1500);
 }
 collectPosts_(job,map);
 updateOverlay_(job, map.size, max, `Đã hoàn tất! Thu thập ${map.size} video.`);
 return {job_id:job.job_id,channel_id:job.channel_id,posts:[...map.values()].slice(0,max),partial:map.size>=max||!reachedEnd||unknown,error:''};
}
if(typeof window!=='undefined'&&!window.__fbStudioV3){
 window.__fbStudioV3={active:null,result:null};
 chrome.runtime.onMessage.addListener((request,sender,sendResponse)=>{
  if(request.action!=='START_SCAN')return;
  const state=window.__fbStudioV3,job=request.job;
  if(!job?.job_id||!job.channel){sendResponse({ok:false});return;}
  const deliver=()=>chrome.runtime.sendMessage({action:'SCAN_RESULT',result:state.result}).catch(()=>{});
  if(state.result?.job_id===job.job_id){deliver();sendResponse({ok:true,state:'complete'});return;}
  if(state.active===job.job_id){sendResponse({ok:true,state:'running'});return;}
  if(state.active){sendResponse({ok:false,error:'Trang đang quét công việc khác.'});return;}
  state.active=job.job_id;state.result=null;
  sendResponse({ok:true,state:'started'});
  scan_(job).then(r=>{state.result=r;}).catch(e=>{state.result={job_id:job.job_id,channel_id:job.channel_id,posts:[],partial:false,error:String(e.message||e).slice(0,500)};}).finally(()=>{state.active=null;deliver();});
 });
}
