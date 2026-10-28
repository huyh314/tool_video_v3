const token=document.getElementById('token'),enabled=document.getElementById('enabled'),box=document.getElementById('status');
async function refresh(){
 const s=await chrome.storage.local.get(['localToken','enabled','lastStatus','lastUpdated','lastError','activeScan','pendingResult']);
 if(document.activeElement!==token)token.value=s.localToken||'';
 enabled.checked=s.enabled!==false;
 box.textContent=(s.lastStatus||'Chưa có kết nối. Chạy Tool 1 rồi nhập mã ghép nối.')+(s.pendingResult?'\nCó kết quả đang chờ gửi.':'')+(s.activeScan?'\nKênh: '+(s.activeScan.job.channel.name||s.activeScan.job.channel.url):'')+(s.lastUpdated?'\nCập nhật: '+new Date(s.lastUpdated).toLocaleString('vi-VN'):'');
 box.style.borderColor=s.lastError?'#dd6b61':'#d7e2ef';
}
document.getElementById('save').addEventListener('click',async()=>{
 const button=document.getElementById('save');
 if(!token.value.trim()){box.textContent='Nhập mã ghép nối từ cấu hình Tool 1.';return;}
 button.disabled=true;
 try{
  await chrome.storage.local.set({localToken:token.value.trim(),enabled:enabled.checked});
  const r=await chrome.runtime.sendMessage({action:'CHECK_CONNECTION'});
  if(!r?.ok)box.textContent=r?.error||'Chưa kết nối được.';
  else await refresh();
 }catch{box.textContent='Không kết nối được service worker. Hãy tải lại extension.';}
 finally{button.disabled=false;}
});
document.getElementById('poll').addEventListener('click',()=>chrome.runtime.sendMessage({action:'POLL_NOW'}).then(refresh));
chrome.storage.onChanged.addListener(()=>refresh());
refresh();
