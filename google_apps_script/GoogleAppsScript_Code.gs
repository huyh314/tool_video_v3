/** Video Studio v3: deploy as owner, set API_TOKEN via menu. Old sheets are preserved. */
const V3_TABLES = {
 channels:{name:'V3 · Kênh theo dõi',id:'channel_id',columns:[
 ['channel_id','Mã kênh'],['name','Tên kênh'],['url','Link fanpage'],['enabled','Bật theo dõi'],
 ['interval_minutes','Chu kỳ (phút)'],['scope_days','Phạm vi (ngày)'],['max_posts','Giới hạn bài/lượt'],['brand','Thương hiệu đầu ra'],
 ['last_scan_at','Lần quét thành công'],['status','Trạng thái'],['error','Thông tin / Lỗi'],['action','Lệnh'],['next_retry_at','Thử lại sau']]},
 posts:{name:'V3 · Bài và video gốc',id:'post_id',columns:[
 ['post_id','Mã bài'],['channel_id','Mã kênh'],['post_url','Link video gốc'],['video_id','Mã video'],['caption','Caption gốc'],
 ['published_at','Ngày đăng'],['collected_at','Lần thu thập'],['likes','Lượt thích'],['comments','Bình luận'],['shares','Chia sẻ'],
 ['direct_video_url','URL media (tạm)'],['download_path','File video trên máy'],['extraction','Nội dung trích xuất (JSON)'],
 ['analysis_status','Trạng thái phân tích'],['error','Lỗi'],['action','Lệnh']]},
 scripts:{name:'V3 · Kịch bản',id:'script_id',columns:[
 ['script_id','Mã kịch bản'],['post_id','Mã bài nguồn'],['version','Phiên bản'],['hook','HOOK'],['items','Các ý (mỗi dòng một ý)'],
 ['caption','Caption mới'],['brand','Thương hiệu đầu ra'],['template','Mẫu (auto/list/pages)'],['duration_seconds','Thời lượng giây (0=tự động)'],
 ['status','Trạng thái duyệt'],['approved_hash','Mã nội dung đã duyệt'],['render_status','Trạng thái dựng'],['error','Lỗi'],['action','Lệnh'],['approved_at','Thời điểm duyệt']]},
 renders:{name:'V3 · Video thành phẩm',id:'render_id',columns:[
 ['render_id','Mã thành phẩm'],['script_id','Mã kịch bản'],['version','Phiên bản'],['content_hash','Mã nội dung'],
 ['output_path','File MP4 trên máy'],['preview_path','File xem trước trên máy'],['duration_seconds','Thời lượng (giây)'],
 ['width','Chiều rộng'],['height','Chiều cao'],['status','Trạng thái'],['created_at','Thời điểm tạo']]},
 jobs:{name:'_V3_Jobs',id:'job_id',columns:[
 ['job_id','job_id'],['kind','kind'],['entity_id','entity_id'],['worker_id','worker_id'],['lease_until','lease_until'],
 ['status','status'],['snapshot_json','snapshot_json'],['result_id','result_id'],['created_at','created_at'],['error','error']]}
};

function onOpen(){
 try{
  SpreadsheetApp.getUi().createMenu('🎬 Video Studio v3')
  .addItem('1. Khởi tạo bảng v3 (giữ dữ liệu cũ)','setupV3')
  .addItem('2. Đặt mã kết nối API','setApiToken').addSeparator()
  .addItem('Nhập danh sách kênh từ bảng cũ (giữ nguyên bảng cũ)','importLegacyChannels')
  .addItem('Quét các kênh đang chọn','scanSelectedChannels')
  .addItem('Duyệt các kịch bản đang chọn','approveSelectedScripts')
  .addItem('Thử lại các dòng đang chọn','retrySelectedRows').addToUi();
 }catch(e){
  console.log('onOpen chỉ gọi UI khi mở trên tab Google Sheet: '+e);
 }
}
function setApiTokenDirect(){
 const token='XfHmPbuEy0vgQru22uX1xI_Ox-M8PrlzaUn5Kn9eKw8';
 PropertiesService.getScriptProperties().setProperty('API_TOKEN',token);
 console.log('Đã lưu mã API kết nối thành công: '+token);
}
function spreadsheet_(){
  const p=PropertiesService.getScriptProperties(),id=p.getProperty('SPREADSHEET_ID');
  const ss=id?SpreadsheetApp.openById(id):SpreadsheetApp.getActiveSpreadsheet();
  if(!ss)throw new Error('SETUP_REQUIRED: Chạy setupV3 trong bảng tính trước.');return ss;
}
function setupV3(){
 const ss=SpreadsheetApp.getActiveSpreadsheet() || (()=>{
  const id=PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID') || '1aCobth9da-qXX3f3yMunSXOzCyRe-qXpVnvFjKf0i3g';
  try{return SpreadsheetApp.openById(id);}catch(e){return null;}
 })();
 if(!ss)throw new Error('Mở Apps Script từ Google Sheet để khởi tạo.');
 PropertiesService.getScriptProperties().setProperty('SPREADSHEET_ID',ss.getId());
 if(!PropertiesService.getScriptProperties().getProperty('API_TOKEN')){
  PropertiesService.getScriptProperties().setProperty('API_TOKEN','XfHmPbuEy0vgQru22uX1xI_Ox-M8PrlzaUn5Kn9eKw8');
 }
 Object.keys(V3_TABLES).forEach(key=>{
  const d=V3_TABLES[key];let s=ss.getSheetByName(d.name);if(!s)s=ss.insertSheet(d.name);
  if(s.getLastRow()===0){
   s.getRange(1,1,1,d.columns.length).setValues([d.columns.map(x=>x[1])]);
   s.getRange(1,1,1,d.columns.length).setNotes([d.columns.map(x=>'API: '+x[0])]);
   s.getRange(1,1,1,d.columns.length).setBackground('#16324f').setFontColor('#ffffff').setFontWeight('bold');
   s.setFrozenRows(1);s.setColumnWidths(1,d.columns.length,150);
  }else assertHeaders_(s,d);
  if(key==='jobs')s.hideSheet();
 });
 const validation=(key,col,values)=>{
  const d=V3_TABLES[key],s=ss.getSheetByName(d.name),i=d.columns.findIndex(x=>x[0]===col)+1;
  s.getRange(2,i,s.getMaxRows()-1,1).setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(values,true).setAllowInvalid(false).build());
 };
 validation('channels','enabled',['TRUE','FALSE']);validation('channels','action',['SCAN','']);
 validation('posts','action',['RETRY','SKIP','']);validation('scripts','template',['auto','list','pages']);validation('scripts','action',['RETRY','']);
 ['channels','posts','scripts','renders'].forEach(key=>{
  const d=V3_TABLES[key],s=ss.getSheetByName(d.name);
  d.columns.forEach((c,i)=>{if(['caption','hook','items','error','extraction'].includes(c[0]))s.setColumnWidth(i+1,300);});
 });
 try{onOpen();SpreadsheetApp.getUi().alert('Đã tạo bảng v3. Thêm tên + link fanpage ở bảng Kênh, để trống Mã kênh. Đặt mã API giống cấu hình trên máy.');}
 catch(e){console.log('Đã tạo bảng v3. Tải lại Google Sheet để mở menu Video Studio v3.');}
}
function setApiToken(){
 const ui=SpreadsheetApp.getUi(),r=ui.prompt('Mã kết nối API','Dán sheet_token từ cấu hình cục bộ (ít nhất 24 ký tự). Không đặt mã trong ô Sheet.',ui.ButtonSet.OK_CANCEL);
 if(r.getSelectedButton()!==ui.Button.OK)return;
 const token=r.getResponseText().trim();if(token.length<24)throw new Error('Mã phải có ít nhất 24 ký tự.');
 PropertiesService.getScriptProperties().setProperty('API_TOKEN',token);ui.alert('Đã lưu mã kết nối.');
}
function doGet(){return json_({status:'error',code:'POST_REQUIRED',message:'Sử dụng POST có token.'});}
function doPost(e){
 let lock;
 try{
  const raw=e&&e.postData&&e.postData.contents;if(!raw||raw.length>1000000)throw new Error('INVALID_REQUEST: Payload trống hoặc quá lớn.');
  const d=JSON.parse(raw),expected=PropertiesService.getScriptProperties().getProperty('API_TOKEN');
  if(!expected||!constantTimeEqual_(String(d.token||''),expected))throw new Error('UNAUTHORIZED: Mã kết nối không hợp lệ hoặc chưa cấu hình.');
  lock=LockService.getScriptLock();if(!lock.tryLock(20000))throw new Error('BUSY: Bảng đang xử lý yêu cầu khác.');
  return json_({status:'success',...dispatch_(d)});
 }catch(e){
  const message=String(e.message||e).slice(0,500);return json_({status:'error',code:message.split(':')[0],message});
 }finally{if(lock)try{lock.releaseLock();}catch(_){}}
}
function json_(x){return ContentService.createTextOutput(JSON.stringify(x)).setMimeType(ContentService.MimeType.JSON);}
function constantTimeEqual_(a,b){let diff=a.length^b.length;for(let i=0;i<Math.max(a.length,b.length);i++)diff|=(a.charCodeAt(i)||0)^(b.charCodeAt(i)||0);return diff===0;}
function dispatch_(d){
 switch(d.action){
  case 'ping':return {protocol:3,spreadsheet_id:PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID')||''};
  case 'claim_scan':return claimScan_(d);case 'complete_scan':return completeScan_(d);
  case 'claim_post':return claimPost_(d);case 'complete_post':return completePost_(d);case 'fail_post':return failPost_(d);
  case 'claim_render':return claimRender_(d);case 'complete_render':return completeRender_(d);case 'fail_render':return failRender_(d);
  case 'renew_lease':return renewLease_(d);default:throw new Error('UNKNOWN_ACTION: Lệnh API không hợp lệ.');
 }
}
function assertHeaders_(s,d){const h=s.getRange(1,1,1,d.columns.length).getValues()[0];if(d.columns.some((x,i)=>h[i]!==x[1]))throw new Error('SCHEMA_CHANGED: Không đổi tên/thứ tự cột bảng '+d.name);}
function table_(key){const d=V3_TABLES[key],s=spreadsheet_().getSheetByName(d.name);if(!s)throw new Error('SETUP_REQUIRED: Chưa có '+d.name);assertHeaders_(s,d);return s;}
function readRows_(key){
 const d=V3_TABLES[key],s=table_(key);if(s.getLastRow()<2)return [];
 return s.getRange(2,1,s.getLastRow()-1,d.columns.length).getValues().map((cells,index)=>{
  const o={__row:index+2};d.columns.forEach((c,i)=>o[c[0]]=cells[i] instanceof Date?cells[i].toISOString():cells[i]);
  if(key==='scripts')o.items=parseItems_(o.items);return o;
 }).filter(x=>d.columns.some(c=>x[c[0]]!==''&&x[c[0]]!==null));
}
function cellValue_(v){
 if(v===null||v===undefined)return '';if(typeof v==='object')v=JSON.stringify(v);
 if(typeof v==='string'){if(v.length>45000)throw new Error('VALUE_TOO_LARGE: Dữ liệu vượt kích thước một ô.');return /^[=+\-@]/.test(v)?"'"+v:v;}return v;
}
function save_(key,row){
 const d=V3_TABLES[key],s=table_(key),id=String(row[d.id]||'');if(!id)throw new Error('MISSING_ID: '+d.id);
 const rows=readRows_(key),matches=rows.filter(r=>String(r[d.id])===id);if(matches.length>1)throw new Error('DUPLICATE_ID: '+d.name);
 let old=matches[0];
 if(!old&&key==='channels'&&row.__row){const x=rows.find(r=>r.__row===row.__row);if(x&&!x.channel_id&&x.url===row.url)old=x;}
 const combined={...(old||{}),...row};const target=old?old.__row:s.getLastRow()+1;
 if(target>s.getMaxRows())s.insertRowsAfter(s.getMaxRows(),target-s.getMaxRows());
 if(old&&String(s.getRange(target,1).getValue()||'')!==String(old[d.id]||''))throw new Error('ROW_MOVED: Bảng vừa đổi thứ tự, hãy thử lại.');
 // Preserve unrelated manually edited fields on existing rows.
 if(old){
  d.columns.forEach((c,i)=>{if(Object.prototype.hasOwnProperty.call(row,c[0])){
   const v=key==='scripts'&&c[0]==='items'?parseItems_(row.items).join('\n'):row[c[0]];s.getRange(target,i+1).setValue(cellValue_(v));
  }});
 }else s.getRange(target,1,1,d.columns.length).setValues([d.columns.map(c=>cellValue_(key==='scripts'&&c[0]==='items'?parseItems_(combined.items).join('\n'):combined[c[0]]))]);
 return combined;
}
function get_(key,id){const k=V3_TABLES[key].id,rows=readRows_(key).filter(x=>String(x[k])===String(id));if(rows.length>1)throw new Error('DUPLICATE_ID: '+id);return rows[0]||null;}
function now_(){return new Date().toISOString();}
function num_(v,def,min,max){const n=Number(v);return Number.isFinite(n)&&v!==''&&v!==undefined?Math.min(max,Math.max(min,Math.floor(n))):def;}
function text_(v,max=20000){return String(v===null||v===undefined?'':v).trim().slice(0,max);}
function id_(v){v=text_(v,160);if(!/^[a-zA-Z0-9_-]{1,160}$/.test(v))throw new Error('INVALID_ID: Định danh không hợp lệ.');return v;}
function parseItems_(v){
 if(Array.isArray(v))return v.map(x=>String(x).trim()).filter(Boolean);if(typeof v!=='string'||!v.trim())return [];
 try{const a=JSON.parse(v);if(Array.isArray(a))return a.map(x=>String(x).trim()).filter(Boolean);}catch(_){}
 return v.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
}
function normalizedScript_(s){
 const duration=Number(s.duration_seconds||0);
 if(typeof s.duration_seconds==='boolean'||!Number.isInteger(duration)||duration<0||duration>600)throw new Error('INVALID_DURATION: Thời lượng phải là số nguyên từ 0 đến 600 giây.');
 let items=s.items;
 if(typeof items==='string'){try{items=JSON.parse(items);}catch(_){items=items.split(/\r?\n/).filter(x=>x.trim());}}
 if(!Array.isArray(items)||items.some(x=>typeof x!=='string'))throw new Error('INVALID_SCRIPT: Các ý phải là văn bản.');
 const o={...s,hook:String(s.hook||'').trim(),items:items.map(x=>x.trim()),caption:String(s.caption||'').trim(),brand:String(s.brand||'').trim(),template:String(s.template||'auto').trim(),duration_seconds:duration};
 if(!o.hook||o.hook.length>240||!o.items.length||o.items.length>20||o.items.some(x=>!x||x.length>500)||o.brand.length>100||o.caption.length>5000)throw new Error('INVALID_SCRIPT: Hook 1–240 ký tự; 1–20 ý, mỗi ý 1–500 ký tự; thương hiệu tối đa 100 ký tự.');
 if(new Set(o.items.map(x=>x.toLowerCase())).size!==o.items.length)throw new Error('INVALID_SCRIPT: Có ý trùng nhau.');
 if(!['auto','list','pages'].includes(o.template))throw new Error('INVALID_TEMPLATE: Chọn auto/list/pages.');return o;
}
function scriptHash_(s){
 const n=normalizedScript_(s),a=[n.hook,n.items,n.caption,n.brand,n.template,n.duration_seconds];
 return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,JSON.stringify(a),Utilities.Charset.UTF_8).map(b=>('0'+((b+256)%256).toString(16)).slice(-2)).join('');
}
function leaseSeconds_(d){return num_(d.lease_seconds,900,60,3600);}
function activeJob_(kind,id){return readRows_('jobs').find(j=>j.kind===kind&&String(j.entity_id)===String(id)&&j.status==='RUNNING'&&Date.parse(j.lease_until)>Date.now());}
function newJob_(kind,id,d,snapshot){
 const worker=id_(d.worker_id);
 readRows_('jobs').filter(j=>j.kind===kind&&String(j.entity_id)===String(id)&&j.status==='RUNNING').forEach(j=>save_('jobs',{job_id:j.job_id,status:'SUPERSEDED'}));
 const j={job_id:'job_'+Utilities.getUuid(),kind,entity_id:String(id),worker_id:worker,lease_until:new Date(Date.now()+leaseSeconds_(d)*1000).toISOString(),status:'RUNNING',snapshot_json:JSON.stringify(snapshot||{}),created_at:now_()};
 save_('jobs',j);return j;
}
function requireJob_(d,kind,entity){
 const j=get_('jobs',id_(d.job_id));if(!j||j.kind!==kind||String(j.entity_id)!==String(entity))throw new Error('STALE_JOB: Công việc không còn hợp lệ.');
 if(j.status==='DONE')return j;
 if(j.status!=='RUNNING'||j.worker_id!==d.worker_id)throw new Error('STALE_OWNER: Công việc đã được giao cho tiến trình khác.');return j;
}
function finishJob_(j,resultId){save_('jobs',{job_id:j.job_id,status:'DONE',result_id:resultId||'',lease_until:''});}
function enabled_(v){return ![false,0,'FALSE','false','0','Tắt','OFF'].includes(v);}
function channelPublic_(c){return {...c,enabled:enabled_(c.enabled),interval_minutes:num_(c.interval_minutes,60,1,10080),scope_days:num_(c.scope_days,7,1,90),max_posts:num_(c.max_posts,10,1,100),brand:text_(c.brand||'chú Dũng Sức',120)};}
function fbUrl_(u){return /^https:\/\/(?:[a-z0-9-]+\.)?facebook\.com\//i.test(String(u));}
function videoIdFromUrl_(u){
 if(!fbUrl_(u))return '';
 const path=String(u).split('?')[0],m=path.match(/\/(?:reel|videos)\/(?:[^/]+\/)?(\d+)(?:\/|$)/);
 if(m)return m[1];
 if(/\/(?:watch\/?|video\.php)$/.test(path)){const v=String(u).match(/[?&]v=(\d+)(?:&|#|$)/);if(v)return v[1];}
 return '';
}
function claimScan_(d){
 for(let c of readRows_('channels')){
  if(!enabled_(c.enabled)||!c.url)continue;
  if(!fbUrl_(c.url)){save_('channels',{...c,channel_id:c.channel_id||'channel_'+Utilities.getUuid(),status:'INVALID_URL',error:'Cần link https://www.facebook.com/...'});continue;}
  if(!c.channel_id){c.channel_id='channel_'+Utilities.getUuid();save_('channels',c);}
  c=channelPublic_(c);if(activeJob_('scan',c.channel_id))continue;
  const manual=String(c.action).toUpperCase()==='SCAN';
  if(!manual&&Date.parse(c.next_retry_at)>Date.now())continue;
  if(!manual&&Date.parse(c.last_scan_at)+c.interval_minutes*60000>Date.now())continue;
  const j=newJob_('scan',c.channel_id,d,{channel:c});save_('channels',{channel_id:c.channel_id,status:'SCANNING',action:'',error:''});
  return {job:{job_id:j.job_id,worker_id:j.worker_id,channel_id:c.channel_id,channel:c}};
 }return {job:null};
}
function completeScan_(d){
 const j=requireJob_(d,'scan',d.channel_id);if(j.status==='DONE')return {duplicate:true};
 if(!Array.isArray(d.posts)||d.posts.length>100)throw new Error('INVALID_POSTS: Danh sách bài không hợp lệ.');
 let count=0;
 d.posts.forEach(p=>{
  const postId=id_(p.post_id),vid=text_(p.video_id,80);
  if(!/^\d+$/.test(vid)||postId!=='fb_'+vid||videoIdFromUrl_(p.post_url)!==vid)throw new Error('INVALID_POST: Bài cần đúng ID và URL video Facebook.');
  const old=get_('posts',postId),m={post_id:postId,channel_id:d.channel_id,post_url:p.post_url,video_id:vid,caption:text_(p.caption),published_at:p.published_at||'',collected_at:p.collected_at||now_(),likes:p.likes==null?'':p.likes,comments:p.comments==null?'':p.comments,shares:p.shares==null?'':p.shares,direct_video_url:text_(p.direct_video_url,10000)};
  save_('posts',old?m:{...m,analysis_status:'PENDING',error:'',action:''});count++;
 });
 const error=text_(d.error,500),partial=d.partial===true,status=error?'FAILED':partial?'PARTIAL':count?'DONE':'EMPTY';
 const patch={channel_id:d.channel_id,status,error:error||(partial?'Lượt quét có giới hạn hoặc thiếu thời gian đăng; chưa xác nhận quét hết.':count?'':'Không tìm thấy video đủ định danh trong lượt này.'),next_retry_at:error?new Date(Date.now()+300000).toISOString():''};
 if(!error)patch.last_scan_at=now_();save_('channels',patch);finishJob_(j,d.channel_id);return {count,partial,status_detail:status};
}
function claimPost_(d){
 for(const p of readRows_('posts')){
  if(p.action==='SKIP'||activeJob_('post',p.post_id))continue;
  if(!['PENDING','RUNNING'].includes(p.analysis_status)&&p.action!=='RETRY')continue;
  const ch=get_('channels',p.channel_id)||{},j=newJob_('post',p.post_id,d,{post_id:p.post_id});
  save_('posts',{post_id:p.post_id,analysis_status:'RUNNING',error:'',action:''});
  return {job:{job_id:j.job_id,worker_id:j.worker_id,post:p,brand:ch.brand||'chú Dũng Sức'}};
 }return {job:null};
}
function completePost_(d){
 const j=requireJob_(d,'post',d.post_id);if(j.status==='DONE')return {duplicate:true};
 const e=d.extraction;if(!e||!text_(e.source_text)||e.uncertain!==false)throw new Error('NEEDS_REVIEW: Chưa xác nhận được nội dung nguồn.');
 const s=normalizedScript_(d.script||{});s.script_id='script_'+id_(d.post_id);s.post_id=d.post_id;
 if(!get_('scripts',s.script_id))save_('scripts',{...s,version:1,status:'READY_FOR_REVIEW',approved_hash:'',render_status:'',error:'',action:''});
 save_('posts',{post_id:d.post_id,download_path:text_(d.download_path,2000),extraction:e,analysis_status:'DONE',error:''});
 finishJob_(j,s.script_id);return {script_id:s.script_id};
}
function failPost_(d){
 const j=requireJob_(d,'post',d.post_id);if(j.status==='DONE')return {duplicate:true};
 const patch={post_id:d.post_id,analysis_status:'FAILED',error:text_(d.error,500)};
 if(d.download_path)patch.download_path=text_(d.download_path,2000);if(d.extraction)patch.extraction=d.extraction;
 save_('posts',patch);finishJob_(j,d.post_id);return {failed:true};
}
function approveScript_(s){
 const n=normalizedScript_(s),hash=scriptHash_(n),version=num_(s.version,1,1,100000)+(s.approved_hash&&s.approved_hash!==hash?1:0);
 const approved={...n,version,status:'APPROVED',approved_hash:hash,approved_at:now_(),error:'',action:''};
 if(s.approved_hash!==hash)approved.render_status='';save_('scripts',approved);Object.assign(s,approved);return approved;
}
function claimRender_(d){
 for(const s of readRows_('scripts')){
  if(s.status!=='APPROVED')continue;
  let hash;try{hash=scriptHash_(s);}catch(e){save_('scripts',{script_id:s.script_id,status:'NEEDS_REAPPROVAL',error:text_(e.message,500)});continue;}
  if(hash!==s.approved_hash){save_('scripts',{script_id:s.script_id,status:'NEEDS_REAPPROVAL',error:'Nội dung đã đổi sau khi duyệt.'});continue;}
  if(activeJob_('render',s.script_id))continue;
  if(['DONE','FAILED'].includes(s.render_status)&&s.action!=='RETRY')continue;
  const renderId='render_'+s.script_id+'_v'+num_(s.version,1,1,100000)+'_'+hash.slice(0,16),snapshot={script:normalizedScript_(s),content_hash:hash,render_id:renderId};
  const j=newJob_('render',s.script_id,d,snapshot);save_('scripts',{script_id:s.script_id,render_status:'RUNNING',error:'',action:''});
  return {job:{job_id:j.job_id,worker_id:j.worker_id,...snapshot}};
 }return {job:null};
}
function completeRender_(d){
 const r=d.render||{},j=requireJob_(d,'render',r.script_id);if(j.status==='DONE')return {duplicate:true};
 const snapshot=JSON.parse(j.snapshot_json);
 if(r.render_id!==snapshot.render_id||r.content_hash!==snapshot.content_hash||Number(r.version)!==Number(snapshot.script.version))throw new Error('SNAPSHOT_MISMATCH: Thành phẩm không khớp phiên bản đã nhận.');
 if(!text_(r.output_path)||!(Number(r.duration_seconds)>0)||!(Number(r.width)>0)||!(Number(r.height)>0))throw new Error('INVALID_RENDER: Thiếu thông tin thành phẩm hợp lệ.');
 save_('renders',{...r,status:'DONE',created_at:r.created_at||now_()});
 const s=get_('scripts',r.script_id);let matches=false;try{matches=s&&scriptHash_(s)===r.content_hash;}catch(_){}
 if(s)save_('scripts',{script_id:s.script_id,render_status:matches?'DONE':'OUTDATED',status:matches?s.status:'NEEDS_REAPPROVAL',error:matches?'':'Thành phẩm thuộc bản cũ. Duyệt lại nội dung mới.'});
 finishJob_(j,r.render_id);return {render_id:r.render_id,outdated:!matches};
}
function failRender_(d){const j=requireJob_(d,'render',d.script_id);if(j.status==='DONE')return {duplicate:true};save_('scripts',{script_id:d.script_id,render_status:'FAILED',error:text_(d.error,500)});finishJob_(j,d.script_id);return {failed:true};}
function renewLease_(d){
 const j=get_('jobs',id_(d.job_id));if(!j||j.status!=='RUNNING'||j.worker_id!==d.worker_id)throw new Error('STALE_OWNER: Không thể gia hạn công việc.');
 const until=new Date(Date.now()+leaseSeconds_(d)*1000).toISOString();save_('jobs',{job_id:j.job_id,lease_until:until});return {lease_until:until};
}
function selected_(key){
 const ss=SpreadsheetApp.getActiveSpreadsheet(),s=ss.getActiveSheet();if(s.getName()!==V3_TABLES[key].name)throw new Error('Hãy chọn dòng trong bảng '+V3_TABLES[key].name);
 const r=s.getActiveRange(),start=Math.max(2,r.getRow()),end=r.getLastRow();return readRows_(key).filter(x=>x.__row>=start&&x.__row<=end);
}
function menuLocked_(fn){const l=LockService.getScriptLock();if(!l.tryLock(20000))throw new Error('Đang bận, hãy thử lại.');try{return fn();}finally{l.releaseLock();}}
function approveSelectedScripts(){const n=menuLocked_(()=>{let count=0;selected_('scripts').forEach(s=>{approveScript_(s);count++;});return count;});SpreadsheetApp.getUi().alert('Đã duyệt '+n+' kịch bản. Tool 2 sẽ nhận bản nội dung này.');}
function scanSelectedChannels(){menuLocked_(()=>{selected_('channels').forEach(c=>save_('channels',{channel_id:c.channel_id||'channel_'+Utilities.getUuid(),__row:c.__row,url:c.url,action:'SCAN',enabled:true}));});}
function retrySelectedRows(){menuLocked_(()=>{
 const name=SpreadsheetApp.getActiveSpreadsheet().getActiveSheet().getName(),key=name===V3_TABLES.posts.name?'posts':name===V3_TABLES.scripts.name?'scripts':null;
 if(!key)throw new Error('Chọn dòng ở bảng Bài và video gốc hoặc Kịch bản.');
 selected_(key).forEach(x=>save_(key,{[V3_TABLES[key].id]:x[V3_TABLES[key].id],action:'RETRY'}));
});}
function onEdit(e){
 if(!e||!e.range||e.range.getSheet().getName()!==V3_TABLES.scripts.name||e.range.getLastRow()<2)return;
 const cols=V3_TABLES.scripts.columns,affected=cols.slice(e.range.getColumn()-1,e.range.getLastColumn()).some(x=>['hook','items','caption','brand','template','duration_seconds','status'].includes(x[0]));
 if(!affected)return;const l=LockService.getScriptLock();if(!l.tryLock(1000))return;
 try{readRows_('scripts').filter(s=>s.__row>=e.range.getRow()&&s.__row<=e.range.getLastRow()&&s.approved_hash).forEach(s=>{
  let matches=false;try{matches=scriptHash_(s)===s.approved_hash;}catch(_){}
  if(!matches)save_('scripts',{script_id:s.script_id,status:'NEEDS_REAPPROVAL',error:'Đã sửa nội dung; dùng menu Duyệt để xác nhận bản mới.'});
 });}finally{l.releaseLock();}
}

function legacyChannel_(cells){
 const url=text_(cells[2],2000);if(!fbUrl_(url))return null;
 const scope=text_(cells[3]),urlHash=Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,url,Utilities.Charset.UTF_8).map(b=>('0'+((b+256)%256).toString(16)).slice(-2)).join('');
 return {channel_id:'channel_'+urlHash.slice(0,20),name:text_(cells[1],300),url,enabled:!scope.toLowerCase().includes('tạm dừng'),interval_minutes:60,scope_days:scope.includes('24h')||scope.includes('hôm nay')?1:scope.includes('3 ngày')?3:7,max_posts:10,brand:text_(cells[4]||'chú Dũng Sức',100),status:'IMPORTED',action:'',error:''};
}
function importLegacyChannels(){
 const outcome=menuLocked_(()=>{
  const ss=spreadsheet_(),old=ss.getSheetByName('📋 Danh Sách Kênh');
  if(!old||old.getLastRow()<2)return {added:0,skipped:0};
  if(old.getLastColumn()<7)throw new Error('LEGACY_SCHEMA: Bảng cũ cần đúng 7 cột của phiên bản trước.');
  const headers=old.getRange(1,1,1,7).getValues()[0];
  if(!String(headers[2]).toLowerCase().includes('link'))throw new Error('LEGACY_SCHEMA: Không nhận diện được cột Link ở bảng cũ.');
  const known=new Set(readRows_('channels').map(c=>String(c.url).replace(/\/$/,'')));
  let added=0,skipped=0;
  old.getRange(2,1,old.getLastRow()-1,7).getValues().forEach(cells=>{
   const ch=legacyChannel_(cells);if(!ch||known.has(ch.url.replace(/\/$/,''))){skipped++;return;}
   save_('channels',ch);known.add(ch.url.replace(/\/$/,''));added++;
  });return {added,skipped};
 });
 SpreadsheetApp.getUi().alert('Đã thêm '+outcome.added+' kênh; bỏ qua '+outcome.skipped+' dòng trùng/không hợp lệ. Bảng cũ được giữ nguyên.');
}
