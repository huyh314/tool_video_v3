// Persistent workflow: chrome.storage holds jobs and undelivered results.
// The transient busy flag only prevents overlapping events within this worker instance.
const API_BASE = 'http://127.0.0.1:8765';
const ALARM = 'studio-v3-poll';
let busy = false;

function isFacebookUrl(url) {
  try { const u=new URL(url);return u.protocol==='https:'&&(u.hostname==='facebook.com'||u.hostname.endsWith('.facebook.com')); }
  catch { return false; }
}
async function api(path, body) {
  const {localToken}=await chrome.storage.local.get('localToken');
  if(!localToken)throw new Error('Chưa có mã ghép nối Tool 1.');
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
  try {
    const response=await fetch(API_BASE+path,{
      method:body===undefined?'GET':'POST',
      headers:{'X-Local-Token':localToken,...(body===undefined?{}:{'Content-Type':'application/json'})},
      body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal
    });
    if(!response.ok)throw new Error(response.status===401?'Mã ghép nối không đúng.':'Tool 1 trả lỗi HTTP '+response.status+'.');
    const data=await response.json();if(data.ok===false||data.status==='error')throw new Error(String(data.error||data.message||'Tool 1 báo lỗi.').slice(0,300));
    return data;
  } catch(e) {
    if(e.name==='AbortError')throw new Error('Tool 1 không trả lời trong thời gian cho phép.');
    if(e instanceof TypeError)throw new Error('Không kết nối được Tool 1. Hãy chạy 1_Theo_Doi_Va_Kich_Ban.bat.');
    throw e;
  } finally {clearTimeout(timer);}
}
async function status(message,error=false){await chrome.storage.local.set({lastStatus:message,lastError:error,lastUpdated:new Date().toISOString()});}
async function ensureAlarm(){
  const current=await chrome.alarms.get(ALARM);
  if(!current)await chrome.alarms.create(ALARM,{periodInMinutes:0.5});
}
async function closeOwnedTab(active){
  if(active&&Number.isInteger(active.tabId)){try{await chrome.tabs.remove(active.tabId);}catch{}}
}
async function flushPending(){
  const {pendingResult,activeScan}=await chrome.storage.local.get(['pendingResult','activeScan']);
  if(!pendingResult)return false;
  const response=await api('/api/scan/result',pendingResult);
  if(response.ok!==true)throw new Error('Tool 1 chưa xác nhận lưu kết quả; sẽ gửi lại.');
  // Remove the acknowledged result before closing. If the worker stops here, tick cleans the old tab.
  await chrome.storage.local.set({pendingResult:null,activeScan:null,cleanupTab:activeScan?.tabId??null});
  await closeOwnedTab(activeScan);await chrome.storage.local.remove('cleanupTab');
  await status(pendingResult.error?'Đã gửi lỗi quét: '+pendingResult.error:'Đã gửi '+pendingResult.posts.length+' video'+(pendingResult.partial?' (lượt quét có giới hạn).':'.'),Boolean(pendingResult.error));
  return true;
}
async function queueError(active,message){
  const result={job_id:active.job.job_id,channel_id:active.job.channel_id,posts:[],partial:false,error:message};
  await chrome.storage.local.set({pendingResult:result});await flushPending();
}
async function startOrResume(active){
  if(Date.now()-active.started_at>240000){await queueError(active,'Quét quá 4 phút. Có thể trang chưa tải hoặc cần đăng nhập Facebook.');return;}
  if(!Number.isInteger(active.tabId)){
    let targetUrl = active.job.channel.url;
    if (targetUrl.includes('profile.php')) {
      if (targetUrl.includes('sk=reels') && !targetUrl.includes('sk=reels_tab')) {
        targetUrl = targetUrl.replace('sk=reels', 'sk=reels_tab');
      } else if (!targetUrl.includes('sk=')) {
        targetUrl = targetUrl + (targetUrl.includes('?') ? '&' : '?') + 'sk=reels_tab';
      }
    } else if (!targetUrl.includes('/reels')) {
      targetUrl = targetUrl.replace(/\/+$/, '') + '/reels/';
    }
    const tab=await chrome.tabs.create({url:targetUrl,active:true});
    active.tabId=tab.id;await chrome.storage.local.set({activeScan:active});
  }
  let tab;try{tab=await chrome.tabs.get(active.tabId);}catch{await queueError(active,'Tab quét đã đóng trước khi hoàn thành.');return;}
  if(!isFacebookUrl(tab.url||tab.pendingUrl||'')){await queueError(active,'Tab quét đã chuyển sang địa chỉ không phải Facebook.');return;}
  if(tab.status!=='complete'){await status('Đang mở kênh '+(active.job.channel.name||active.job.channel.url));return;}
  // Content script is declared statically; its result arrives via SCAN_RESULT even after a worker restart.
  try {
    const ack=await chrome.tabs.sendMessage(active.tabId,{action:'START_SCAN',job:active.job});
    if(!ack?.ok)throw new Error('Trang chưa sẵn sàng quét.');
    await status('Đang quét '+(active.job.channel.name||active.job.channel.url));
  } catch(e) {
    await status('Chờ trang Facebook sẵn sàng; tự thử lại trong 30 giây.',false);
  }
}
async function tick(){
  if(busy)return;busy=true;
  try{
    await ensureAlarm();
    const settings=await chrome.storage.local.get(['localToken','enabled','pendingResult','activeScan','cleanupTab']);
    if(Number.isInteger(settings.cleanupTab)){try{await chrome.tabs.remove(settings.cleanupTab);}catch{}await chrome.storage.local.remove('cleanupTab');}
    // Pending results must be flushed even when polling was subsequently disabled.
    if(settings.pendingResult){await flushPending();return;}
    if(settings.enabled===false||!settings.localToken)return;
    let active=settings.activeScan;
    if(!active){
      const response=await api('/api/scan');
      if(!response.job){await status('Đã kết nối Tool 1. Đang chờ kênh đến lịch quét.');return;}
      const job=response.job;
      if(!job.job_id||!job.channel_id||!isFacebookUrl(job.channel?.url))throw new Error('Tool 1 gửi công việc thiếu ID hoặc URL Facebook không hợp lệ.');
      active={job,tabId:null,started_at:Date.now()};
      await chrome.storage.local.set({activeScan:active});
    }
    await startOrResume(active);
  }catch(e){await status(String(e.message||e).slice(0,400),true);}
  finally{busy=false;}
}

chrome.runtime.onInstalled.addListener(()=>{ensureAlarm().then(tick).catch(()=>{});});
chrome.runtime.onStartup.addListener(()=>{ensureAlarm().then(tick).catch(()=>{});});
chrome.alarms.onAlarm.addListener(alarm=>{if(alarm.name===ALARM)tick();});
chrome.tabs.onUpdated.addListener((tabId,info)=>{if(info.status==='complete')chrome.storage.local.get('activeScan').then(({activeScan})=>{if(activeScan?.tabId===tabId)tick();});});
chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
  if(message.action==='SCAN_RESULT'){
    (async()=>{
      const {activeScan,pendingResult}=await chrome.storage.local.get(['activeScan','pendingResult']);
      if(!activeScan||sender.tab?.id!==activeScan.tabId||message.result?.job_id!==activeScan.job.job_id)throw new Error('Kết quả không khớp tab/công việc hiện tại.');
      const r=message.result;
      if(!Array.isArray(r.posts)||r.posts.length>100)throw new Error('Danh sách bài không hợp lệ.');
      // First result is durable and immutable until acknowledgement.
      if(!pendingResult)await chrome.storage.local.set({pendingResult:{job_id:r.job_id,channel_id:activeScan.job.channel_id,posts:r.posts,partial:r.partial===true,error:String(r.error||'').slice(0,500)}});
      sendResponse({ok:true});tick();
    })().catch(e=>sendResponse({ok:false,error:e.message}));
    return true;
  }
  if(message.action==='CHECK_CONNECTION'&&!sender.tab){
    api('/api/health').then(r=>{if(r.ok!==true||r.protocol!==3)throw new Error('Tool 1 không đúng phiên bản v3.');return status('Đã kết nối Tool 1 v3.');}).then(()=>{sendResponse({ok:true});tick();}).catch(e=>{status(e.message,true);sendResponse({ok:false,error:e.message});});
    return true;
  }
  if(message.action==='POLL_NOW'&&!sender.tab){tick().then(()=>sendResponse({ok:true}));return true;}
});
