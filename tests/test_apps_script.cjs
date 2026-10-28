const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function fixture() {
  let seq = 0;
  const tables = {channels: [], posts: [], scripts: [], renders: [], jobs: []};
  const c = vm.createContext({console, Date, JSON, Math, Utilities: {
    getUuid: () => `uuid-${++seq}`,
    DigestAlgorithm: {SHA_256: 'sha256'}, Charset: {UTF_8: 'utf8'},
    computeDigest: (algo, text) => [...crypto.createHash('sha256').update(text).digest()],
  }, PropertiesService: {getScriptProperties: () => ({getProperty: key => key === 'API_TOKEN' ? 'test-secret-long-enough' : null})},
  LockService: {getScriptLock: () => ({tryLock: () => true, releaseLock() {}})},
  ContentService: {MimeType: {JSON: 'json'}, createTextOutput: text => ({text, setMimeType() {return this;}})},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../google_apps_script/GoogleAppsScript_Code.gs'), 'utf8'), c);
  c.readRows_ = key => tables[key].map(x => JSON.parse(JSON.stringify(x)));
  c.save_ = (key, row) => {
    const idKey = {channels: 'channel_id', posts: 'post_id', scripts: 'script_id', renders: 'render_id', jobs: 'job_id'}[key];
    const i = tables[key].findIndex(x => x[idKey] === row[idKey]);
    if (i >= 0) tables[key][i] = JSON.parse(JSON.stringify({...tables[key][i], ...row}));
    else tables[key].push(JSON.parse(JSON.stringify(row)));
    return row;
  };
  const call = (action, args={}) => JSON.parse(JSON.stringify(c.dispatch_({action, ...args})));
  return {c, tables, call};
}

test('hash matches Python compact UTF-8 array contract', () => {
  const {c} = fixture();
  const s = {hook:' TIÊU ĐỀ ', items:[' Ý thứ nhất ', 'Ý thứ hai'], caption:' Chú thích ', brand:'Tên kênh',template:'pages',duration_seconds:25};
  const expected = crypto.createHash('sha256').update(JSON.stringify(['TIÊU ĐỀ',['Ý thứ nhất','Ý thứ hai'],'Chú thích','Tên kênh','pages',25])).digest('hex');
  assert.equal(c.scriptHash_(s), expected);
});

test('scan claims are exclusive; disabled channel never runs; retry result deduplicated', () => {
  const {tables, call} = fixture();
  tables.channels.push({channel_id:'off',url:'https://www.facebook.com/off',enabled:false,action:'SCAN'},
    {channel_id:'ch1',name:'Nguồn',url:'https://www.facebook.com/source',enabled:true,interval_minutes:60,max_posts:5});
  const {job} = call('claim_scan', {worker_id:'w1'});
  assert.equal(job.channel_id, 'ch1');
  assert.equal(call('claim_scan', {worker_id:'w2'}).job, null);
  const payload = {job_id:job.job_id,worker_id:'w1',channel_id:'ch1',posts:[{post_id:'fb_123',video_id:'123',post_url:'https://www.facebook.com/reel/123',caption:'Một bài',collected_at:new Date().toISOString()}]};
  assert.throws(() => call('complete_scan', {...payload,worker_id:'wrong'}), /STALE|OWNER/);
  call('complete_scan', payload);
  call('complete_scan', payload);
  assert.equal(tables.posts.length, 1);
  assert.equal(tables.posts[0].analysis_status, 'PENDING');
});

test('expired job can be reclaimed and previous worker cannot commit', () => {
  const {tables, call} = fixture();
  tables.posts.push({post_id:'fb_1',channel_id:'ch',analysis_status:'PENDING'});
  const j1 = call('claim_post', {worker_id:'old'}).job;
  tables.jobs[0].lease_until = '2000-01-01T00:00:00.000Z';
  const j2 = call('claim_post', {worker_id:'new'}).job;
  assert.ok(j2);
  assert.notEqual(j1.job_id, j2.job_id);
  assert.throws(() => call('fail_post',{job_id:j1.job_id,worker_id:'old',post_id:'fb_1',error:'late'}), /STALE/);
  call('fail_post',{job_id:j2.job_id,worker_id:'new',post_id:'fb_1',error:'test'});
  assert.equal(call('claim_post',{worker_id:'new'}).job,null);
  tables.posts[0].action='RETRY';
  assert.ok(call('claim_post',{worker_id:'new'}).job);
});

test('post completion does not overwrite an edited script on retry', () => {
  const {tables, call} = fixture();
  tables.posts.push({post_id:'fb_1',analysis_status:'PENDING'});
  const j=call('claim_post',{worker_id:'w'}).job;
  const payload={job_id:j.job_id,worker_id:'w',post_id:'fb_1',download_path:'D:\\source.mp4',extraction:{source_text:'Nguồn thật',segments:[],uncertain:false},script:{script_id:'script_fb_1',post_id:'fb_1',hook:'HOOK',items:['Nội dung'],caption:'',brand:'Kênh',template:'auto',duration_seconds:0}};
  call('complete_post',payload);
  tables.scripts[0].hook='Anh đã sửa';
  call('complete_post',payload);
  assert.equal(tables.scripts[0].hook,'Anh đã sửa');
  assert.notEqual(tables.scripts[0].status,'APPROVED');
});

test('only approved unchanged script renders; editing invalidates approval', () => {
  const {c,tables,call}=fixture();
  const s={script_id:'script_fb_1',post_id:'fb_1',hook:'HOOK',items:['Một ý'],caption:'',brand:'Kênh',template:'auto',duration_seconds:0,version:1,status:'READY_FOR_REVIEW'};
  tables.scripts.push(s);
  assert.equal(call('claim_render',{worker_id:'r'}).job,null);
  c.approveScript_(s);
  s.hook='Đã sửa sau duyệt';
  c.save_('scripts',s);
  assert.equal(call('claim_render',{worker_id:'r'}).job,null);
  assert.equal(tables.scripts[0].status,'NEEDS_REAPPROVAL');
});

test('render commits old version explicitly; duplicate callbacks never duplicate rows', () => {
  const {c,tables,call}=fixture();
  const s={script_id:'script_fb_1',post_id:'fb_1',hook:'HOOK',items:['Một ý'],caption:'',brand:'Kênh',template:'auto',duration_seconds:0,version:1,status:'READY_FOR_REVIEW'};
  tables.scripts.push(s); c.approveScript_(s);
  const j=call('claim_render',{worker_id:'r'}).job;
  assert.ok(j.content_hash);
  tables.scripts[0].hook='Nội dung mới';
  const payload={job_id:j.job_id,worker_id:'r',render:{render_id:j.render_id,script_id:j.script.script_id,version:j.script.version,content_hash:j.content_hash,output_path:'D:\\result.mp4',preview_path:'D:\\preview.png',duration_seconds:20,width:720,height:1280,status:'DONE'}};
  call('complete_render',payload); call('complete_render',payload);
  assert.equal(tables.renders.length,1);
  assert.equal(tables.scripts[0].status,'NEEDS_REAPPROVAL');
  assert.equal(tables.renders[0].content_hash,j.content_hash);
});

test('API requires token and returns structured errors', () => {
  const {c}=fixture();
  const req=data=>JSON.parse(c.doPost({postData:{contents:JSON.stringify(data)}}).text);
  assert.equal(req({action:'ping',token:'bad'}).status,'error');
  assert.equal(req({action:'ping',token:'test-secret-long-enough'}).protocol,3);
  assert.equal(req({action:'no-such-action',token:'test-secret-long-enough'}).status,'error');
});

test('empty brand hash parity and invalid duration are explicit',()=>{
 const {c}=fixture();const s={hook:'H',items:['Ý'],caption:'',brand:'',template:'auto',duration_seconds:0};
 assert.equal(c.scriptHash_(s),crypto.createHash('sha256').update(JSON.stringify(['H',['Ý'],'','','auto',0])).digest('hex'));
 assert.throws(()=>c.scriptHash_({...s,duration_seconds:1.2}),/INVALID_DURATION/);
 assert.throws(()=>c.scriptHash_({...s,items:['Ý','Ý']}),/INVALID_SCRIPT/);
});

test('partial failure after writing render can retry without duplicates',()=>{
 const {c,tables,call}=fixture();const s={script_id:'s1',post_id:'p1',hook:'H',items:['Một ý'],caption:'',brand:'',template:'auto',duration_seconds:0,version:1,status:'READY_FOR_REVIEW'};
 tables.scripts.push(s);c.approveScript_(s);const j=call('claim_render',{worker_id:'r'}).job;
 const payload={job_id:j.job_id,worker_id:'r',render:{render_id:j.render_id,script_id:s.script_id,version:1,content_hash:j.content_hash,output_path:'x.mp4',duration_seconds:10,width:720,height:1280}};
 const original=c.save_;let fail=true;c.save_=(key,value)=>{if(key==='scripts'&&fail){fail=false;throw new Error('simulated interrupted write');}return original(key,value);};
 assert.throws(()=>call('complete_render',payload),/interrupted/);
 assert.equal(tables.renders.length,1);assert.equal(tables.jobs[0].status,'RUNNING');
 call('complete_render',payload);assert.equal(tables.renders.length,1);assert.equal(tables.jobs[0].status,'DONE');
});

test('failed scan preserves successful timestamp and applies retry cooldown',()=>{
 const {tables,call}=fixture();tables.channels.push({channel_id:'ch',url:'https://www.facebook.com/test',enabled:true,last_scan_at:'2020-01-01T00:00:00Z'});
 const j=call('claim_scan',{worker_id:'w'}).job;
 call('complete_scan',{job_id:j.job_id,worker_id:'w',channel_id:'ch',posts:[],error:'Login needed'});
 assert.equal(tables.channels[0].last_scan_at,'2020-01-01T00:00:00Z');assert.equal(tables.channels[0].status,'FAILED');
 assert.equal(call('claim_scan',{worker_id:'w'}).job,null);
});

test('mismatched media identity is rejected before storing the post',()=>{
 const {tables,call}=fixture();tables.channels.push({channel_id:'ch',url:'https://www.facebook.com/test',enabled:true});
 const j=call('claim_scan',{worker_id:'w'}).job;
 assert.throws(()=>call('complete_scan',{job_id:j.job_id,worker_id:'w',channel_id:'ch',posts:[{post_id:'fb_123',video_id:'123',post_url:'https://www.facebook.com/reel/999'}]}),/INVALID_POST/);
 assert.equal(tables.posts.length,0);
});

test('render identity includes approved version when content reverts',()=>{
 const {c,tables,call}=fixture();const s={script_id:'s1',post_id:'p1',hook:'H',items:['Một ý'],caption:'',brand:'',template:'auto',duration_seconds:0,version:3,status:'READY_FOR_REVIEW'};
 tables.scripts.push(s);c.approveScript_(s);const j=call('claim_render',{worker_id:'r'}).job;
 assert.match(j.render_id,/^render_s1_v3_/);assert.equal(j.script.version,3);
});

test('legacy channel conversion keeps scope, pause and source brand',()=>{
 const {c}=fixture();const ch=c.legacyChannel_([1,'Nguồn','https://www.facebook.com/source','Quét 3 ngày qua','Kênh mới','','']);
 assert.equal(ch.scope_days,3);assert.equal(ch.brand,'Kênh mới');assert.equal(ch.enabled,true);
 assert.equal(c.legacyChannel_([1,'Nguồn','https://www.facebook.com/source','Tạm dừng quét','','','']).enabled,false);
 assert.equal(c.legacyChannel_([1,'X','https://example.com/','','','','']),null);
});

